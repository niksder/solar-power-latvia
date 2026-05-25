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
ENERGY_PRICES_DIR = os.getenv('ENERGY_PRICES_DIR')
ENERGY_SOURCES_DIR = os.getenv('ENERGY_SOURCES_DIR')
TOTAL_PRODUCTION_DIR = os.getenv('TOTAL_PRODUCTION_DIR', 'total_production')
WEATHER_DATA_DIR = os.getenv('WEATHER_DATA_DIR')
OUTPUTS_DIR = os.getenv('OUTPUTS_DIR', 'outputs')

MERGED_PANEL_DATA_PATH = os.path.join(PANEL_DATA_DIR, 'merged_panel_data.csv')

df = pd.read_csv(MERGED_PANEL_DATA_PATH, dtype={'bzone': 'category'})
df['time'] = pd.to_datetime(df['time'], utc=True, format='mixed')
_derived_suffixes = ('_share', '_prod_yearly', '_prod_growth', '_share_growth')
_derived_cols = [c for c in df.columns if any(c.endswith(s) for s in _derived_suffixes)]
df = df.drop(columns=['policy0', 'policy1'] + _derived_cols, errors='ignore')
df = df.dropna(subset=['time'])
df = df.sort_values(['bzone', 'time']).reset_index(drop=True)


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


def _rolling_precipitation(group):
    group = group.set_index('time').sort_index()
    precip = group['precipitation'].fillna(0)
    group['precipitation_24h'] = precip.rolling('1D', min_periods=1).sum()
    group['precipitation_weekly'] = precip.rolling('7D', min_periods=1).sum()
    group['precipitation_monthly'] = precip.rolling('30D', min_periods=1).sum()
    return group.reset_index()


def process_merged_data():
    # This function is called from main.py after downloading and merging the data.
    # It adds rolling shares, growth rates, accumulated precipitation, and policy columns.
        
    # Process one zone at a time and write directly to CSV to avoid accumulating
    # a full second copy of the DataFrame in memory (as groupby.apply would).
    prod_cols_added = [c for c in PRODUCTION_COLS if c in df.columns]
    bzones = df['bzone'].unique().tolist()
    write_header = True

    for i, bzone in enumerate(bzones):
        mask = df['bzone'] == bzone
        group = df.loc[mask].copy()
        group = _rolling_shares(group)
        group = _rolling_precipitation(group)
        group = group.sort_values('time').reset_index(drop=True)
        is_latvia_group = group['bzone'] == 'Latvia'
        group['policy0'] = (is_latvia_group & (group['time'] >= '2020-04-01')).astype(int) # https://www.elektrum.lv/lv/majai/par-mums/jaunumi/likuma-izmainas-veicinas-saules-energijas-izmantosanu-latvija/
        group['policy1'] = (is_latvia_group & (group['time'].dt.year >= 2024)).astype(int) # https://www.kem.gov.lv/lv/jaunums/apstiprinats-regulejums-atlauju-sanemsanai-saules-veja-parku-uzkratuvju-vai-hibridprojektu-attistibai-latvija-0
        group['time'] = group['time'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        group.to_csv(MERGED_PANEL_DATA_PATH, mode='w' if write_header else 'a', header=write_header, index=False)
        write_header = False
        del group
        gc.collect()
        print(f'  [{i + 1}/{len(bzones)}] wrote {bzone}')

    prefixes_added = [c[:-len('_production')] for c in prod_cols_added]
    print(f'Added rolling shares/yearly/growth for: {prefixes_added}; accumulated precipitation; policy columns. Wrote to {MERGED_PANEL_DATA_PATH}')

    del df
    gc.collect()

if __name__ == '__main__':
    process_merged_data()