import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()
PANEL_DATA_DIR = os.getenv('PANEL_DATA_DIR')
OUTPUTS_DIR = os.getenv('OUTPUTS_DIR', 'outputs')

MERGED_PANEL_DATA_PATH = os.path.join(PANEL_DATA_DIR, 'merged_panel_data.csv')

df = pd.read_csv(MERGED_PANEL_DATA_PATH, usecols=['bzone', 'sun', 'year'])

years = [2019, 2020, 2021, 2022, 2023]
df = df[df['year'].isin(years)]

# Sum solar radiance per bzone per year
yearly = df.groupby(['bzone', 'year'])['sun'].sum().reset_index()

bzones = sorted(yearly['bzone'].unique())
n_bzones = len(bzones)
n_years = len(years)

x = np.arange(n_bzones)
width = 0.15
offsets = np.linspace(-(n_years - 1) / 2, (n_years - 1) / 2, n_years) * width

fig, ax = plt.subplots(figsize=(max(16, n_bzones * 0.6), 7))

colors = plt.cm.tab10(np.linspace(0, 0.5, n_years))

for i, year in enumerate(years):
    vals = [
        yearly.loc[(yearly['bzone'] == bz) & (yearly['year'] == year), 'sun'].values[0]
        if len(yearly.loc[(yearly['bzone'] == bz) & (yearly['year'] == year)]) > 0 else 0
        for bz in bzones
    ]
    ax.bar(x + offsets[i], vals, width=width, label=str(year), color=colors[i])

ax.set_xticks(x)
ax.set_xticklabels(bzones, rotation=45, ha='right', fontsize=9)
ax.set_xlabel('Bidding Zone')
ax.set_ylabel('Total Annual Solar Radiance (sum of hourly values)')
ax.set_title('Yearly Solar Radiance by Bidding Zone (2019–2023)')
ax.legend(title='Year')
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{v/1e6:.1f}M' if v >= 1e6 else f'{v/1e3:.0f}k'))

plt.tight_layout()
plt.savefig(os.path.join(OUTPUTS_DIR, 'solar_radiance_by_bzone.png'), dpi=150)
plt.show()
