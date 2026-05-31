import gc
import os
import sys
import numpy as np
import pandas as pd
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(__file__))
from merge_panel import COLUMN_TRANSLATIONS

PRODUCTION_COLS = [v for v in COLUMN_TRANSLATIONS.values() if v.endswith('_production')]

load_dotenv()
PANEL_DATA_DIR = os.getenv('PANEL_DATA_DIR')
DATA_DIR = os.getenv('DATA_DIR')
CONSTANTS_DIR = os.path.join(DATA_DIR, os.getenv('CONSTANTS_DIR', 'constants'))
ENERGY_PRICES_DIR = os.getenv('ENERGY_PRICES_DIR')
ENERGY_SOURCES_DIR = os.getenv('ENERGY_SOURCES_DIR')
TOTAL_PRODUCTION_DIR = os.getenv('TOTAL_PRODUCTION_DIR', 'total_production')
WEATHER_DATA_DIR = os.getenv('WEATHER_DATA_DIR')
OUTPUTS_DIR = os.getenv('OUTPUTS_DIR', 'outputs')

RUSSIA_GAS_IMPORTS_FILE = os.path.join(CONSTANTS_DIR, 'nrg_ti_gas__russia.csv')   # https://ec.europa.eu/eurostat/databrowser/view/nrg_ti_gas__custom_21610563/default/table 
TOTAL_GAS_CONSUMPTION_FILE = os.path.join(CONSTANTS_DIR, 'nrg_cb_gas__total.csv') # https://ec.europa.eu/eurostat/databrowser/view/nrg_cb_gas__custom_21610648/default/table 

MERGED_PANEL_DATA_PATH = os.path.join(PANEL_DATA_DIR, 'merged_panel_data.csv')
COUNTRY_PANEL_DATA_PATH = os.path.join(PANEL_DATA_DIR, 'country_panel_data.csv')

# Columns added by process_merged_data.py — drop before aggregating
_DERIVED_SUFFIXES = ('_share', '_prod_yearly', '_prod_growth', '_share_growth')
_PROCESS_COLS = ['policy0', 'policy1', 'russia_dependency',
                 'precipitation_24h', 'precipitation_weekly', 'precipitation_monthly']

_SUM_COLS = set(PRODUCTION_COLS + ['total_generation'])
_MEAN_COLS = {'energy_price', 'temperature', 'sun', 'precipitation', 'wind_u100', 'wind_v100', 'wind'}
_FIRST_COLS = {'year', 'month', 'week_of_year', 'day_of_week', 'hour', 'country_code', 'gdp_pps', 'population_density'}


def generate_country_data():
    """Aggregate merged_panel_data.csv from bidding zones to countries.

    Streams merged_panel_data.csv in chunks, accumulating one country at a time
    (the file is sorted by bzone, and bzones for the same country are adjacent).
    Each country is aggregated and written before the next is loaded, so peak
    memory is proportional to the largest single country rather than the full file.

    Aggregation: production/generation columns are summed; price and weather
    columns are averaged; time/metadata columns take the first value per group.

    Writes the result to country_panel_data.csv in PANEL_DATA_DIR.
    """
    from main import BIDDING_ZONES

    bzone_to_country = {z['name']: z['countries'][0] for z in BIDDING_ZONES}

    tmp_path = COUNTRY_PANEL_DATA_PATH + '.tmp'
    write_header = True
    current_country = None
    current_rows = []
    agg = None  # built once from the first chunk's columns
    n_written = 0

    def _flush(country_name, rows):
        nonlocal write_header, n_written
        group = pd.concat(rows, ignore_index=True)
        agg_df = group.groupby('time', sort=True).agg(agg).reset_index()
        agg_df.insert(0, 'country', country_name)
        agg_df['time'] = agg_df['time'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        agg_df.to_csv(tmp_path, mode='w' if write_header else 'a', header=write_header, index=False)
        write_header = False
        n_written += 1
        print(f'  [{n_written}] wrote {country_name} ({len(agg_df)} rows)')
        del group, agg_df
        gc.collect()

    try:
        for chunk in pd.read_csv(MERGED_PANEL_DATA_PATH, chunksize=50_000, dtype={'bzone': str}):
            # Drop columns added by process_merged_data.py
            derived_cols = [c for c in chunk.columns if any(c.endswith(s) for s in _DERIVED_SUFFIXES)]
            chunk = chunk.drop(columns=_PROCESS_COLS + derived_cols, errors='ignore')

            chunk['time'] = pd.to_datetime(chunk['time'], utc=True, format='mixed')
            chunk = chunk.dropna(subset=['time'])

            chunk['country'] = chunk['bzone'].map(bzone_to_country)
            unmapped = chunk['country'].isna().sum()
            if unmapped:
                print(f'Warning: {unmapped} rows with unmapped bzone dropped.')
            chunk = chunk.dropna(subset=['country'])
            chunk = chunk.drop(columns=['bzone'])

            # Build agg dict once from first chunk's columns
            if agg is None:
                agg = {}
                for col in chunk.columns:
                    if col in ('country', 'time'):
                        continue
                    if col in _SUM_COLS:
                        agg[col] = 'sum'
                    elif col in _MEAN_COLS:
                        agg[col] = 'mean'
                    elif col in _FIRST_COLS:
                        agg[col] = 'first'

            # File is sorted by bzone; bzones for the same country are contiguous.
            # Detect country boundaries and flush completed countries.
            for country in chunk['country'].unique():
                c_rows = chunk[chunk['country'] == country].drop(columns=['country']).copy()
                if current_country is None:
                    current_country = country
                if country != current_country:
                    _flush(current_country, current_rows)
                    current_rows = []
                    current_country = country
                current_rows.append(c_rows)

        if current_rows:
            _flush(current_country, current_rows)

        os.replace(tmp_path, COUNTRY_PANEL_DATA_PATH)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    print(f'Done. Wrote {n_written} countries to {COUNTRY_PANEL_DATA_PATH}')
    gc.collect()


if __name__ == '__main__':
    generate_country_data()

