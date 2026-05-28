"""
Plot the energy mix of a single bidding zone over time as a stacked area chart.

Usage:
    python country_energy_mix.py <bzone>

Example:
    python country_energy_mix.py Latvia
    python country_energy_mix.py "SE1"
"""
import argparse
import os
import sys

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
PANEL_DATA_DIR = os.getenv('PANEL_DATA_DIR')
OUTPUTS_DIR = os.getenv('OUTPUTS_DIR', 'outputs')

MERGED_PANEL_DATA_PATH = os.path.join(PANEL_DATA_DIR, 'merged_panel_data.csv')

OUT_DIR = os.path.join(OUTPUTS_DIR, 'panel', 'others')

# ── Source display names ────────────────────────────────────────────────────────────────────────────
SOURCE_LABELS = {
    'gas_prod_yearly':        'Gas',
    'brown_coal_prod_yearly': 'Brown coal',
    'coal_gas_prod_yearly':   'Coal gas',
    'hard_coal_prod_yearly':  'Hard coal',
    'oil_prod_yearly':        'Oil',
    'oil_shale_prod_yearly':  'Oil shale',
    'peat_prod_yearly':       'Peat',
    'hydro_ps_prod_yearly':   'Hydro (pumped storage)',
    'hydro_ror_prod_yearly':  'Hydro (run-of-river)',
    'hydro_wr_prod_yearly':   'Hydro (water reservoir)',
    'wind_off_prod_yearly':   'Wind offshore',
    'wind_on_prod_yearly':    'Wind onshore',
    'solar_prod_yearly':      'Solar',
}

# ── Source colors — edit hex values here to change the palette ────────────────────────────────────────────
SOURCE_COLORS = {
    'gas_prod_yearly':        "#ca1313",  # red
    'brown_coal_prod_yearly': '#8B4513',  # saddle brown
    'coal_gas_prod_yearly':   '#6b6b6b',  # medium grey
    'hard_coal_prod_yearly':  '#222222',  # near-black
    'oil_prod_yearly':        '#5C3317',  # dark brown
    'oil_shale_prod_yearly':  '#c8a96e',  # tan
    'peat_prod_yearly':       '#7a5c2e',  # mud brown
    'hydro_ps_prod_yearly':   '#08519c',  # deep blue
    'hydro_ror_prod_yearly':  '#6baed6',  # light blue
    'hydro_wr_prod_yearly':   '#2171b5',  # medium blue
    'wind_off_prod_yearly':   '#41ab5d',  # teal green
    'wind_on_prod_yearly':    '#74c476',  # light green
    'solar_prod_yearly':      '#ffd700',  # gold
}

ALL_SOURCES = list(SOURCE_LABELS.keys())


def plot_energy_mix(bzone: str) -> None:
    usecols = ['bzone', 'time', 'total_generation'] + ALL_SOURCES
    df = pd.read_csv(MERGED_PANEL_DATA_PATH, usecols=usecols, dtype={'bzone': 'category'})
    df['time'] = pd.to_datetime(df['time'], utc=True, format='mixed')

    df = df[df['bzone'] == bzone]
    if df.empty:
        available = pd.read_csv(MERGED_PANEL_DATA_PATH, usecols=['bzone'])['bzone'].unique().tolist()
        print(f"No data found for bzone '{bzone}'.")
        print("Available bzones:", ', '.join(sorted(available)))
        sys.exit(1)

    df = df.set_index('time').sort_index()
    df['total_gen_yearly'] = df['total_generation'].rolling('365D').sum()
    monthly = df[ALL_SOURCES + ['total_gen_yearly']].resample('ME').mean()

    # Only plot sources that have at least some non-zero data for this zone
    present = [col for col in ALL_SOURCES if monthly[col].gt(0).any()]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.stackplot(
        monthly.index,
        [monthly[col].fillna(0).values for col in present],
        labels=[SOURCE_LABELS[col] for col in present],
        colors=[SOURCE_COLORS[col] for col in present],
        alpha=0.9,
    )
    ax.plot(monthly.index, monthly['total_gen_yearly'].values, color='black',
            linewidth=1.5, linestyle='--', label='Total generation')
    ax.set_title(f'Energy mix — {bzone}', fontsize=14)
    ax.set_xlabel('Date')
    ax.set_ylabel('Production (MWh, rolling 365-day)')
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=9, frameon=False)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    fig.tight_layout()

    os.makedirs(OUT_DIR, exist_ok=True)
    safe_name = bzone.replace(' ', '_').lower()
    path = os.path.join(OUT_DIR, f'energy_mix_prod_{safe_name}.png')
    fig.savefig(path, dpi=150)
    print(f'Plot saved to {path}')
    plt.show()
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Plot the energy mix of a bidding zone over time.')
    parser.add_argument('bzone', help='Bidding zone name (e.g. Latvia, Poland, SE1)')
    args = parser.parse_args()
    plot_energy_mix(args.bzone)
