import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from dotenv import load_dotenv

load_dotenv()

PANEL_DATA_DIR = os.getenv('PANEL_DATA_DIR')
OUTPUTS_DIR = os.getenv('OUTPUTS_DIR', 'outputs')

MERGED_PANEL_DATA_PATH = PANEL_DATA_DIR + "/merged_panel_data.csv"
PLOT_OUTPUT_PATH = OUTPUTS_DIR + "/panel/others/latvia_energy_mix_over_time.png"
START_DATE = pd.Timestamp("2017-01-01")
END_DATE = pd.Timestamp("2025-12-31")

# --- Load data ---
df = pd.read_csv(MERGED_PANEL_DATA_PATH, usecols=['bzone', 'year', 'gas_production', 'solar_production', 'total_generation'])
df = df[(df['year'] >= START_DATE.year) & (df['year'] <= END_DATE.year)]

# --- Filter Latvia only ---
lv = df[df['bzone'] == 'Latvia']

# --- Compute annual shares ---
annual = (
    lv.groupby('year')[['gas_production', 'solar_production', 'total_generation']]
    .sum()
    .reset_index()
)
annual['gas_share'] = annual['gas_production'] / annual['total_generation']
annual['solar_share'] = annual['solar_production'] / annual['total_generation']

# --- Line graph ---
os.makedirs(os.path.dirname(PLOT_OUTPUT_PATH), exist_ok=True)

fig, ax = plt.subplots(figsize=(9, 5))

ax.plot(annual['year'], annual['solar_share'] * 100, marker='o', linewidth=2,
        color="#d88f08", label='Solar share')
ax.plot(annual['year'], annual['gas_share'] * 100, marker='o', linewidth=2,
        color="#bb1d1d", label='Natural gas share')

ax.set_title('Latvia: solar and natural gas share of electricity production')
ax.set_xlabel('Year')
ax.set_ylabel('Share of total generation (%)')
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f%%'))
ax.axvline(x=2021.8, color='gray', linestyle='--', linewidth=1.2, alpha=0.6)
ax.legend(frameon=False)
ax.grid(axis='y', linestyle='--', alpha=0.5)
fig.tight_layout()
fig.savefig(PLOT_OUTPUT_PATH, dpi=150)
print(f'\nPlot saved to {PLOT_OUTPUT_PATH}')

