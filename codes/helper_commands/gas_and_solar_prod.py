import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from dotenv import load_dotenv

load_dotenv()
PANEL_DATA_DIR = os.getenv('PANEL_DATA_DIR')
OUTPUTS_DIR = os.getenv('OUTPUTS_DIR', 'outputs')

MERGED_PANEL_DATA_PATH = os.path.join(PANEL_DATA_DIR, 'merged_panel_data.csv')

plot_df = pd.read_csv(
    MERGED_PANEL_DATA_PATH,
    usecols=['bzone', 'time', 'gas_share', 'solar_share', 'gas_prod_yearly', 'solar_prod_yearly'],
    dtype={'bzone': 'category'},
)
plot_df['time'] = pd.to_datetime(plot_df['time'], utc=True, format='mixed')
plot_df = plot_df[plot_df['time'] >= '2017-01-01']

ZONE_COLORS = {
    'Austria':     '#d62728',
    'Croatia':     '#ff7f0e',
    'Czechia':     '#2ca02c',
    'Finland':     '#9467bd',
    'France':      '#8c564b',
    'Latvia':      '#000000',
    'Poland':      '#7f7f7f',
    'Romania':     '#bcbd22',
    'SE1':         '#08519c',
    'SE2':         '#2171b5',
    'SE3':         '#6baed6',
    'SE4':         '#c6dbef',
    'Slovenia':    '#00a86b',
    'Switzerland': '#e8a838',
    'Belgium':     '#e40b82',
    'Germany':     '#520d72',
    'Slovakia':    '#086161',
}

OUT_DIR = os.path.join(OUTPUTS_DIR, 'panel', 'others')
os.makedirs(OUT_DIR, exist_ok=True)


def _save(fig, filename):
    path = os.path.join(OUT_DIR, filename)
    fig.savefig(path, dpi=150)
    print(f'Plot saved to {path}')
    plt.show()
    plt.close(fig)


# --- Rolling gas share ---
fig, ax = plt.subplots(figsize=(13, 6))
for bzone, group in plot_df.groupby('bzone'):
    group = group.set_index('time').sort_index()
    daily = group['gas_share'].resample('D').mean()
    ax.plot(daily.index, daily.values * 100, linewidth=2.5 if bzone == 'Latvia' else 1.2, label=bzone,
            color=ZONE_COLORS.get(bzone))
ax.set_title('Rolling 365-day gas share of total electricity production')
ax.set_xlabel('Date')
ax.set_ylabel('Gas share (%)')
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f%%'))
ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=8, frameon=False)
ax.grid(axis='y', linestyle='--', alpha=0.5)
fig.tight_layout()
_save(fig, 'rolling_gas_share.png')

# --- Rolling solar share ---
fig, ax = plt.subplots(figsize=(13, 6))
for bzone, group in plot_df.groupby('bzone'):
    group = group.set_index('time').sort_index()
    daily = group['solar_share'].resample('D').mean()
    ax.plot(daily.index, daily.values * 100, linewidth=2.5 if bzone == 'Latvia' else 1.2, label=bzone,
            color=ZONE_COLORS.get(bzone))
ax.set_title('Rolling 365-day solar share of total electricity production')
ax.set_xlabel('Date')
ax.set_ylabel('Solar share (%)')
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f%%'))
ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=8, frameon=False)
ax.grid(axis='y', linestyle='--', alpha=0.5)
fig.tight_layout()
_save(fig, 'rolling_solar_share.png')

# --- Rolling gas production (log scale) ---
fig, ax = plt.subplots(figsize=(13, 6))
for bzone, group in plot_df.groupby('bzone'):
    group = group.set_index('time').sort_index()
    daily = group['gas_prod_yearly'].resample('D').mean()
    daily = daily[daily > 0]
    ax.plot(daily.index, daily.values, linewidth=2.5 if bzone == 'Latvia' else 1.2, label=bzone,
            color=ZONE_COLORS.get(bzone))
ax.set_yscale('log')
ax.set_title('Rolling 365-day gas production (log scale)')
ax.set_xlabel('Date')
ax.set_ylabel('Gas production (MWh, log scale)')
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=8, frameon=False)
ax.grid(axis='y', linestyle='--', alpha=0.5)
fig.tight_layout()
_save(fig, 'rolling_gas_production_log.png')

# --- Rolling solar production (log scale) ---
fig, ax = plt.subplots(figsize=(13, 6))
for bzone, group in plot_df.groupby('bzone'):
    group = group.set_index('time').sort_index()
    daily = group['solar_prod_yearly'].resample('D').mean()
    daily = daily[daily > 0]
    ax.plot(daily.index, daily.values, linewidth=2.5 if bzone == 'Latvia' else 1.2, label=bzone,
            color=ZONE_COLORS.get(bzone))
ax.set_yscale('log')
ax.set_title('Rolling 365-day solar production (log scale)')
ax.set_xlabel('Date')
ax.set_ylabel('Solar production (MWh, log scale)')
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=8, frameon=False)
ax.grid(axis='y', linestyle='--', alpha=0.5)
fig.tight_layout()
_save(fig, 'rolling_solar_production_log.png')

dataset_start = plot_df['time'].min()

# --- Gas production growth rate (log difference) ---
fig, ax = plt.subplots(figsize=(13, 6))
for bzone, group in plot_df.groupby('bzone'):
    group = group.set_index('time').sort_index()
    daily = group['gas_prod_yearly'].resample('D').mean()
    log_diff = np.log(daily.replace(0, float('nan'))).diff()
    first_data = daily[daily > 0].index.min()
    if pd.notna(first_data) and first_data > dataset_start:
        log_diff.loc[first_data:first_data + pd.Timedelta(days=365)] = float('nan')
    monthly = log_diff.resample('ME').mean()
    ax.plot(monthly.index, monthly.values, linewidth=2.5 if bzone == 'Latvia' else 1.0, label=bzone,
            color=ZONE_COLORS.get(bzone))
ax.axhline(0, color='black', linewidth=0.8, linestyle='--')
ax.set_title('Gas production growth rate (monthly avg log difference of rolling 365-day production)')
ax.set_xlabel('Date')
ax.set_ylabel('Log difference')
ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=8, frameon=False)
ax.grid(axis='y', linestyle='--', alpha=0.5)
fig.tight_layout()
_save(fig, 'gas_production_growth.png')

# --- Solar production growth rate (log difference) ---
fig, ax = plt.subplots(figsize=(13, 6))
for bzone, group in plot_df.groupby('bzone'):
    group = group.set_index('time').sort_index()
    daily = group['solar_prod_yearly'].resample('D').mean()
    log_diff = np.log(daily.replace(0, float('nan'))).diff()
    first_data = daily[daily > 0].index.min()
    if pd.notna(first_data) and first_data > dataset_start:
        log_diff.loc[first_data:first_data + pd.Timedelta(days=365)] = float('nan')
    monthly = log_diff.resample('ME').mean()
    ax.plot(monthly.index, monthly.values, linewidth=2.5 if bzone == 'Latvia' else 1.0, label=bzone,
            color=ZONE_COLORS.get(bzone))
ax.axhline(0, color='black', linewidth=0.8, linestyle='--')
ax.set_title('Solar production growth rate (monthly avg log difference of rolling 365-day production)')
ax.set_xlabel('Date')
ax.set_ylabel('Log difference')
ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=8, frameon=False)
ax.grid(axis='y', linestyle='--', alpha=0.5)
fig.tight_layout()
_save(fig, 'solar_production_growth.png')
