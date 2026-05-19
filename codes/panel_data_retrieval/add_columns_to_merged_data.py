import gc
import os
import numpy as np
import pandas as pd
from dotenv import load_dotenv

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
df = df.drop(columns=['policy0', 'policy1', 'gas_share', 'solar_share', 'solar_prod_yearly', 'gas_prod_yearly', 'solar_prod_growth', 'solar_share_growth'], errors='ignore')
df = df.dropna(subset=['time'])
df = df.sort_values(['bzone', 'time']).reset_index(drop=True)


def _rolling_shares(group):
    group = group.set_index('time').sort_index()
    rolling_total = group['total_generation'].rolling('365D', min_periods=1).sum()
    rolling_gas = group['gas_production'].fillna(0).rolling('365D', min_periods=1).sum()
    rolling_solar = group['solar_production'].fillna(0).rolling('365D', min_periods=1).sum()
    total_safe = rolling_total.replace(0, float('nan'))
    group['gas_share'] = rolling_gas / total_safe
    group['solar_share'] = rolling_solar / total_safe
    group['solar_prod_yearly'] = rolling_solar
    group['gas_prod_yearly'] = rolling_gas
    log_solar = np.log(rolling_solar.replace(0, float('nan')))
    group['solar_prod_growth'] = log_solar - log_solar.shift(1)
    log_solar_share = np.log(group['solar_share'].replace(0, float('nan')))
    group['solar_share_growth'] = log_solar_share - log_solar_share.shift(1)
    return group.reset_index()


df = df.groupby('bzone', group_keys=False).apply(_rolling_shares)
df = df.sort_values(['bzone', 'time']).reset_index(drop=True)


def _rolling_precipitation(group):
    group = group.set_index('time').sort_index()
    precip = group['precipitation'].fillna(0)
    group['precipitation_24h'] = precip.rolling('1D', min_periods=1).sum()
    group['precipitation_weekly'] = precip.rolling('7D', min_periods=1).sum()
    group['precipitation_monthly'] = precip.rolling('30D', min_periods=1).sum()
    return group.reset_index()


df = df.groupby('bzone', group_keys=False).apply(_rolling_precipitation)
df = df.sort_values(['bzone', 'time']).reset_index(drop=True)
# Since april 1, 2020 — Latvia only
is_latvia = df['bzone'] == 'Latvia'
df['policy0'] = (is_latvia & (df['time'] >= '2020-04-01')).astype(int) # https://www.elektrum.lv/lv/majai/par-mums/jaunumi/likuma-izmainas-veicinas-saules-energijas-izmantosanu-latvija/
df['policy1'] = (is_latvia & (df['time'].dt.year >= 2024)).astype(int) # https://www.kem.gov.lv/lv/jaunums/apstiprinats-regulejums-atlauju-sanemsanai-saules-veja-parku-uzkratuvju-vai-hibridprojektu-attistibai-latvija-0
df['time'] = df['time'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')

df.to_csv(MERGED_PANEL_DATA_PATH, index=False)
print(f'Added gas_share, solar_share, solar_prod_yearly, gas_prod_yearly, solar_prod_growth, solar_share_growth, accumulated precipitation, and policy1 columns. Wrote {len(df)} rows to {MERGED_PANEL_DATA_PATH}')

del df
gc.collect()