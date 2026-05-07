import os
import math
import csv
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
PANEL_DATA_DIR = os.getenv('PANEL_DATA_DIR')

_DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data'))
ENB_SOLAR_FILE = os.path.join(_DEFAULT_DATA_DIR, 'constants', 'ENB010m_20260429-171145.csv')
ENERGY_PRICES_DIR = os.getenv('ENERGY_PRICES_DIR')
ENERGY_SOURCES_DIR = os.getenv('ENERGY_SOURCES_DIR')
TOTAL_PRODUCTION_DIR = os.getenv('TOTAL_PRODUCTION_DIR', 'total_production')
WEATHER_DATA_DIR = os.getenv('WEATHER_DATA_DIR')

COLUMN_TRANSLATIONS = {
    'energy_price': 'energy_price',          # already clean after prefix removal
    'energy_sources_B01': 'biomass_production',
    'energy_sources_B04': 'gas_production',
    'energy_sources_B11': 'hydro_production',
    'energy_sources_B16': 'solar_production',
    'energy_sources_B19': 'wind_production',
    'energy_sources_B20': 'other_production',
    'total_production_total_generation': 'total_generation',
    'weather_u100': 'wind_u100',
    'weather_v100': 'wind_v100',
    'weather_t2m': 'temperature',
    'weather_ssrd': 'sun',
    'weather_tp': 'precipitation',
}


def _resample_to_hourly(df):
    """Resample a merged zone DataFrame to hourly resolution if it is sub-hourly (e.g. 15-min).

    Accumulated fields (sun/ssrd and precipitation/tp) are summed; all other
    numeric columns are averaged.  Non-numeric columns use the first value in
    each hour.  Returns the DataFrame unchanged when the resolution is already
    hourly or coarser.
    """
    dt = pd.to_datetime(df['time'], utc=True, errors='coerce')
    diffs = dt.dropna().sort_values().diff().dropna()
    if diffs.empty or diffs.median() >= pd.Timedelta('55min'):
        return df

    df = df.copy()
    df['time'] = dt
    df = df.set_index('time')

    # Accumulated fields must be summed; everything else is averaged
    sum_cols = [c for c in df.columns if c in ('sun', 'precipitation')]
    agg = {}
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            agg[c] = 'first'
        elif c in sum_cols:
            agg[c] = 'sum'
        else:
            agg[c] = 'mean'

    df = df.resample('h').agg(agg).reset_index()
    df['time'] = df['time'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    return df


def _load_zone(zone):
    """Load and merge the three per-zone CSVs into a single DataFrame with a 'time' index."""
    prices_path = os.path.join(PANEL_DATA_DIR, ENERGY_PRICES_DIR, f'energy_prices_{zone["name"]}.csv')
    sources_path = os.path.join(PANEL_DATA_DIR, ENERGY_SOURCES_DIR, f'energy_sources_{zone["name"]}.csv')
    total_path = os.path.join(PANEL_DATA_DIR, TOTAL_PRODUCTION_DIR, f'total_production_{zone["name"]}.csv')
    weather_path = os.path.join(PANEL_DATA_DIR, WEATHER_DATA_DIR, f'weather_{zone["name"]}.csv')

    missing = [p for p in (prices_path, sources_path, weather_path) if not os.path.exists(p)]
    if missing:
        print(f'Skipping {zone["name"]} in merge — missing files: {missing}')
        return None

    prices = pd.read_csv(prices_path)
    prices = prices.rename(columns={'price': 'energy_price'})

    sources = pd.read_csv(sources_path)
    sources = sources.rename(columns={c: f'energy_sources_{c}' for c in sources.columns if c != 'time'})

    total_prod = None
    if os.path.exists(total_path):
        total_prod = pd.read_csv(total_path)
        total_prod = total_prod.rename(columns={c: f'total_production_{c}' for c in total_prod.columns if c != 'time'})

    weather = pd.read_csv(weather_path)
    weather = weather.rename(columns={'valid_time': 'time'})
    weather = weather.rename(columns={c: f'weather_{c}' for c in weather.columns if c != 'time'})

    df = prices.merge(sources, on='time', how='outer')
    if total_prod is not None:
        df = df.merge(total_prod, on='time', how='left')
    df = df.merge(weather, on='time', how='outer')
    df = df.sort_values('time').reset_index(drop=True)

    # Apply column translations
    df = df.rename(columns=COLUMN_TRANSLATIONS)

    # Resample to hourly if any source provided sub-hourly (e.g. 15-min) data
    df = _resample_to_hourly(df)

    # Compute wind magnitude from components
    if 'wind_u100' in df.columns and 'wind_v100' in df.columns:
        df['wind'] = (df['wind_u100'] ** 2 + df['wind_v100'] ** 2) ** 0.5

    # Add time-derived columns
    dt = pd.to_datetime(df['time'], utc=True, errors='coerce')
    df['year'] = dt.dt.year
    df['month'] = dt.dt.month
    df['week_of_year'] = dt.dt.isocalendar().week.astype('Int64')
    df['day_of_week'] = dt.dt.weekday
    df['hour'] = dt.dt.hour

    df.insert(0, 'bzone', zone['name'])

    return df


def _impute_latvia_2023_solar(df):
    """Fill NaN solar_production for Latvia's 2023 rows using ENB monthly statistics.

    Monthly totals from ENB010m (million kWh → MWh) are distributed
    proportionally to the ``sun`` (ssrd) value in each hour, matching
    the approach in codes/data_retrieval/merge.py.
    """
    if not os.path.exists(ENB_SOLAR_FILE):
        print(f'ENB solar file not found, skipping Latvia 2023 imputation: {ENB_SOLAR_FILE}')
        return df

    # --- Read ENB monthly solar totals ---
    enb_monthly_solar = {}  # {month: total_mwh}
    with open(ENB_SOLAR_FILE, 'r', newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)  # title row
        next(reader)  # blank line
        headers = next(reader)  # "Rādītāji", "2020M01", ...
        for row in reader:
            if not row:
                continue
            if 'saules' not in row[0].lower():
                continue
            for i, col_header in enumerate(headers):
                if i == 0 or 'M' not in col_header:
                    continue
                try:
                    year_str, month_str = col_header.split('M')
                    if int(year_str) != 2023:
                        continue
                    month_key = int(month_str)
                    value_str = (row[i] if i < len(row) else '').strip()
                    if value_str and value_str not in ('…', '..', ''):
                        enb_monthly_solar[month_key] = float(value_str) * 1000  # million kWh → MWh
                except (ValueError, IndexError):
                    continue
            break  # only the solar row needed

    if not enb_monthly_solar:
        print('No 2023 ENB solar data found, skipping imputation.')
        return df

    # --- Impute hour-by-hour within each 2023 month ---
    df = df.copy()
    dt = pd.to_datetime(df['time'], utc=True, errors='coerce')

    for month, monthly_mwh in enb_monthly_solar.items():
        mask_month = (dt.dt.year == 2023) & (dt.dt.month == month)
        mask_missing = mask_month & df['solar_production'].isna()

        if not mask_missing.any():
            continue

        sun_vals = df.loc[mask_month, 'sun'].clip(lower=0).fillna(0)
        total_sun = sun_vals.sum()

        if total_sun > 0:
            df.loc[mask_missing, 'solar_production'] = (
                monthly_mwh * df.loc[mask_missing, 'sun'].clip(lower=0).fillna(0) / total_sun
            )
        else:
            df.loc[mask_missing, 'solar_production'] = 0.0

    return df


def merge_panel(bidding_zones):
    """Merge per-zone CSVs into a single panel dataset.

    For each zone in ``bidding_zones``, loads energy_prices, energy_sources,
    and weather CSVs, joins them on time, adds a ``bzone`` identifier column,
    then stacks all zones and writes the result to
    ``{PANEL_DATA_DIR}/merged_panel_data.csv``.

    Parameters
    ----------
    bidding_zones : list of dict
        The BIDDING_ZONES list from main.py (must have at least ``name``).
    """
    output_path = os.path.join(PANEL_DATA_DIR, 'merged_panel_data.csv')

    frames = []
    for zone in bidding_zones:
        df = _load_zone(zone)
        if df is not None:
            if zone['name'] == 'Latvia':
                df = _impute_latvia_2023_solar(df)
            frames.append(df)
            print(f'Loaded {len(df)} rows for {zone["name"]}')

    if not frames:
        print('No zone data available, skipping panel merge.')
        return

    panel = pd.concat(frames, ignore_index=True)
    panel = panel.sort_values(['bzone', 'time']).reset_index(drop=True)

    panel.to_csv(output_path, index=False)
    print(f'Wrote {len(panel)} rows ({len(frames)} zones) to {output_path}')


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from main import BIDDING_ZONES
    merge_panel(BIDDING_ZONES)

