import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from dotenv import load_dotenv

load_dotenv()

PANEL_DATA_DIR = os.getenv('PANEL_DATA_DIR')
OUTPUTS_DIR = os.getenv('OUTPUTS_DIR', 'outputs')

MERGED_PANEL_DATA_PATH = PANEL_DATA_DIR + "/merged_panel_data.csv"
PLOT_OUTPUT_PATH = OUTPUTS_DIR + "/panel/others/solar_share_of_countries.png"
START_DATE = pd.Timestamp("2020-01-01")
END_DATE = pd.Timestamp("2025-12-31")

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
}

# --- Load data ---
df = pd.read_csv(MERGED_PANEL_DATA_PATH, usecols=['bzone', 'year', 'solar_production', 'total_generation'])
df = df[(df['year'] >= START_DATE.year) & (df['year'] <= END_DATE.year)]

# --- Compute annual gas share per country ---
annual = (
    df.groupby(['bzone', 'year'])[['solar_production', 'total_generation']]
    .sum()
    .reset_index()
)
annual['solar_share'] = annual['solar_production'] / annual['total_generation']

# --- Pivot for table display ---
table = annual.pivot(index='bzone', columns='year', values='solar_share')
table.index.name = 'Country'
table.columns.name = 'Year'

pct_table = (table * 100).round(2)
print("\nSolar share of total electricity production (%) by country and year:")
print(pct_table.to_string(float_format=lambda x: f'{x:.2f}%'))

# --- Line graph ---
os.makedirs(os.path.dirname(PLOT_OUTPUT_PATH), exist_ok=True)

fig, ax = plt.subplots(figsize=(11, 6))

for country, row in table.iterrows():
    valid = row.dropna()
    if valid.empty:
        continue
    ax.plot(valid.index, valid.values * 100, marker='o', linewidth=1.8, label=country,
            color=ZONE_COLORS.get(country))

ax.set_title('Solar share of total electricity production by country')
ax.set_xlabel('Year')
ax.set_ylabel('Solar share (%)')
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f%%'))
ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=8, frameon=False)
ax.grid(axis='y', linestyle='--', alpha=0.5)
fig.tight_layout()
fig.savefig(PLOT_OUTPUT_PATH, dpi=150)
print(f'\nPlot saved to {PLOT_OUTPUT_PATH}')

