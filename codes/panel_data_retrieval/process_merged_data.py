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


def _rolling_shares(group):
    group = group.set_index('time').sort_index()
    rolling_total = group['total_generation'].rolling('365D', min_periods=1).sum()
    total_safe = rolling_total.replace(0, float('nan'))
    prod_cols = [c for c in PRODUCTION_COLS if c in group.columns]
    for col in prod_cols:
        prefix = col[:-len('_production')]
        rolling_prod = group[col].fillna(0).rolling('365D', min_periods=1).sum()
        group[f'{prefix}_share'] = rolling_prod / total_safe
        group[f'{prefix}_prod_yearly'] = rolling_prod
        log_prod = np.log(rolling_prod.replace(0, float('nan')))
        group[f'{prefix}_prod_growth'] = log_prod - log_prod.shift(1)
        log_share = np.log(group[f'{prefix}_share'].replace(0, float('nan')))
        group[f'{prefix}_share_growth'] = log_share - log_share.shift(1)
    return group.reset_index()


def _compute_russia_dependency():
    """Compute Russia gas dependency ratio per country.

    Calculated as total Russian gas imports (2019–2021) divided by total
    inland gas consumption (2019–2021), summed across those three years.
    Returns a DataFrame with columns ['country_code', 'russia_dependency'].
    Returns None if either source file is missing.
    """
    YEARS = [2019, 2020, 2021]

    print('Computing Russia gas dependency ratio per country...')

    if not os.path.exists(RUSSIA_GAS_IMPORTS_FILE):
        print(f'Russia gas imports file not found, skipping russia_dependency: {RUSSIA_GAS_IMPORTS_FILE}')
        return None
    if not os.path.exists(TOTAL_GAS_CONSUMPTION_FILE):
        print(f'Total gas consumption file not found, skipping russia_dependency: {TOTAL_GAS_CONSUMPTION_FILE}')
        return None

    imports = pd.read_csv(RUSSIA_GAS_IMPORTS_FILE)
    imports = imports[imports['partner'] == 'RU']
    imports = imports[['geo', 'TIME_PERIOD', 'OBS_VALUE']].copy()
    imports['TIME_PERIOD'] = pd.to_numeric(imports['TIME_PERIOD'], errors='coerce')
    imports['OBS_VALUE'] = pd.to_numeric(imports['OBS_VALUE'], errors='coerce').fillna(0)
    imports = imports[imports['TIME_PERIOD'].isin(YEARS)]
    imports_sum = imports.groupby('geo')['OBS_VALUE'].sum().rename('imports_sum')

    print(f'Computed total Russian gas imports for {len(imports_sum)} countries. Now computing total gas consumption...')

    consumption = pd.read_csv(TOTAL_GAS_CONSUMPTION_FILE)
    consumption = consumption[['geo', 'TIME_PERIOD', 'OBS_VALUE']].copy()
    consumption['TIME_PERIOD'] = pd.to_numeric(consumption['TIME_PERIOD'], errors='coerce')
    consumption['OBS_VALUE'] = pd.to_numeric(consumption['OBS_VALUE'], errors='coerce').fillna(0)
    consumption = consumption[consumption['TIME_PERIOD'].isin(YEARS)]
    consumption_sum = consumption.groupby('geo')['OBS_VALUE'].sum().rename('consumption_sum')

    print(f'Computed total Russian gas imports and total gas consumption for {len(imports_sum)} countries. Calculating dependency ratio...')

    combined = pd.concat([imports_sum, consumption_sum], axis=1)
    combined['russia_dependency'] = (
        combined['imports_sum'] / combined['consumption_sum'].replace(0, float('nan'))
    )
    return combined[['russia_dependency']].reset_index().rename(columns={'geo': 'country_code'})


def _rolling_precipitation(group):
    group = group.set_index('time').sort_index()
    precip = group['precipitation'].fillna(0)
    group['precipitation_24h'] = precip.rolling('1D', min_periods=1).sum()
    group['precipitation_weekly'] = precip.rolling('7D', min_periods=1).sum()
    group['precipitation_monthly'] = precip.rolling('30D', min_periods=1).sum()
    return group.reset_index()


def process_merged_data():
    # Reads the merged panel CSV in chunks (one bidding zone at a time) so peak
    # memory is proportional to the largest single zone rather than the full file.
    # Writes to a temp file and atomically replaces MERGED_PANEL_DATA_PATH at the end,
    # avoiding a read/write conflict on the same path.
    _derived_suffixes = ('_share', '_prod_yearly', '_prod_growth', '_share_growth')
    russia_dep = _compute_russia_dependency()

    tmp_path = MERGED_PANEL_DATA_PATH + '.tmp'
    write_header = True
    current_bzone = None
    current_rows = []
    prod_cols_present = None
    n_written = 0

    def _flush(bzone_name, rows):
        nonlocal write_header, n_written
        group = pd.concat(rows, ignore_index=True)
        group = _rolling_shares(group)
        group = _rolling_precipitation(group)
        if russia_dep is not None:
            group = group.merge(russia_dep, on='country_code', how='left')
        group = group.sort_values('time').reset_index(drop=True)
        is_latvia_group = group['bzone'] == 'Latvia'
        group['policy0'] = (is_latvia_group & (group['time'] >= '2020-04-01')).astype(int) # https://www.elektrum.lv/lv/majai/par-mums/jaunumi/likuma-izmainas-veicinas-saules-energijas-izmantosanu-latvija/
        group['policy1'] = (is_latvia_group & (group['time'].dt.year >= 2024)).astype(int) # https://www.kem.gov.lv/lv/jaunums/apstiprinats-regulejums-atlauju-sanemsanai-saules-veja-parku-uzkratuvju-vai-hibridprojektu-attistibai-latvija-0
        group['time'] = group['time'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        group.to_csv(tmp_path, mode='w' if write_header else 'a', header=write_header, index=False)
        write_header = False
        n_written += 1
        print(f'  [{n_written}] wrote {bzone_name}')
        del group
        gc.collect()

    try:
        for chunk in pd.read_csv(MERGED_PANEL_DATA_PATH, chunksize=50_000, dtype={'bzone': str}):
            chunk['time'] = pd.to_datetime(chunk['time'], utc=True, format='mixed')
            _derived_cols = [c for c in chunk.columns if any(c.endswith(s) for s in _derived_suffixes)]
            chunk = chunk.drop(columns=['policy0', 'policy1', 'russia_dependency'] + _derived_cols, errors='ignore')
            chunk = chunk.dropna(subset=['time'])

            if prod_cols_present is None:
                prod_cols_present = [c for c in PRODUCTION_COLS if c in chunk.columns]

            # File is sorted by bzone; detect zone boundaries and flush completed zones.
            for bz in chunk['bzone'].unique():
                bz_rows = chunk[chunk['bzone'] == bz].copy()
                if current_bzone is None:
                    current_bzone = bz
                if bz != current_bzone:
                    _flush(current_bzone, current_rows)
                    current_rows = []
                    current_bzone = bz
                current_rows.append(bz_rows)

        if current_rows:
            _flush(current_bzone, current_rows)

        os.replace(tmp_path, MERGED_PANEL_DATA_PATH)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    prefixes_added = [c[:-len('_production')] for c in (prod_cols_present or [])]
    print(f'Added rolling shares/yearly/growth for: {prefixes_added}; accumulated precipitation; policy columns. Wrote to {MERGED_PANEL_DATA_PATH}')
    gc.collect()

if __name__ == '__main__':
    process_merged_data()