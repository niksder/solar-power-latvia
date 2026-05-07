import os
import math
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from dotenv import load_dotenv

load_dotenv()
PANEL_DATA_DIR = os.getenv('PANEL_DATA_DIR')
ENERGY_PRICES_DIR = os.getenv('ENERGY_PRICES_DIR')
ENERGY_SOURCES_DIR = os.getenv('ENERGY_SOURCES_DIR')
TOTAL_PRODUCTION_DIR = os.getenv('TOTAL_PRODUCTION_DIR', 'total_production')
WEATHER_DATA_DIR = os.getenv('WEATHER_DATA_DIR')
OUTPUTS_DIR = os.getenv('OUTPUTS_DIR', 'outputs')

MERGED_PANEL_DATA_PATH = os.path.join(PANEL_DATA_DIR, 'merged_panel_data.csv')

df = pd.read_csv(MERGED_PANEL_DATA_PATH)
df['time'] = pd.to_datetime(df['time'], utc=True, format='mixed')
df = df.drop(columns=['gas_share', 'solar_share'], errors='ignore')
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
df['time'] = df['time'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')

df.to_csv(MERGED_PANEL_DATA_PATH, index=False)
print(f'Added gas_share, solar_share, and accumulated precipitation columns. Wrote {len(df)} rows to {MERGED_PANEL_DATA_PATH}')

# --- Plot rolling gas share ---
ZONE_COLORS = {
    'Austria':     '#d62728',
    'Croatia':     '#ff7f0e',
    'Czechia':     '#2ca02c',
    'Finland':     '#9467bd',
    'France':      '#8c564b',
    'Latvia':      '#e377c2',
    'Poland':      '#7f7f7f',
    'Romania':     '#bcbd22',
    'SE1':         '#08519c',
    'SE2':         '#2171b5',
    'SE3':         '#6baed6',
    'SE4':         '#c6dbef',
    'Slovenia':    '#00a86b',
    'Switzerland': '#e8a838',
    'Belgium':    '#e40b82',
    'Germany':    '#520d72',
    'Slovakia':   '#086161',
}

plot_df = df.copy()
plot_df['time'] = pd.to_datetime(plot_df['time'], utc=True, format='mixed')

fig, ax = plt.subplots(figsize=(13, 6))
for bzone, group in plot_df.groupby('bzone'):
    group = group.set_index('time').sort_index()
    daily = group['gas_share'].resample('D').mean()
    ax.plot(daily.index, daily.values * 100, linewidth=1.2, label=bzone,
            color=ZONE_COLORS.get(bzone))

ax.set_title('Rolling 365-day gas share of total electricity production')
ax.set_xlabel('Date')
ax.set_ylabel('Gas share (%)')
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f%%'))
ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=8, frameon=False)
ax.grid(axis='y', linestyle='--', alpha=0.5)
fig.tight_layout()

plot_path = os.path.join(OUTPUTS_DIR, 'panel', 'others', 'rolling_gas_share.png')
os.makedirs(os.path.dirname(plot_path), exist_ok=True)
fig.savefig(plot_path, dpi=150)
print(f'Plot saved to {plot_path}')
plt.show()

# --- Plot rolling solar share ---
fig2, ax2 = plt.subplots(figsize=(13, 6))
for bzone, group in plot_df.groupby('bzone'):
    group = group.set_index('time').sort_index()
    daily = group['solar_share'].resample('D').mean()
    ax2.plot(daily.index, daily.values * 100, linewidth=1.2, label=bzone,
             color=ZONE_COLORS.get(bzone))

ax2.set_title('Rolling 365-day solar share of total electricity production')
ax2.set_xlabel('Date')
ax2.set_ylabel('Solar share (%)')
ax2.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f%%'))
ax2.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=8, frameon=False)
ax2.grid(axis='y', linestyle='--', alpha=0.5)
fig2.tight_layout()

plot_path2 = os.path.join(OUTPUTS_DIR, 'panel', 'others', 'rolling_solar_share.png')
fig2.savefig(plot_path2, dpi=150)
print(f'Plot saved to {plot_path2}')
plt.show()

