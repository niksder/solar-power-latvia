import os
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()
PANEL_DATA_DIR = os.getenv('PANEL_DATA_DIR')
OUTPUTS_DIR = os.getenv('OUTPUTS_DIR', 'outputs')

MERGED_PANEL_DATA_PATH = os.path.join(PANEL_DATA_DIR, 'merged_panel_data.csv')

df = pd.read_csv(MERGED_PANEL_DATA_PATH, usecols=["country_code", "russia_dependency"])

# One value per country (constant across bidding zones and time)
country_dep = (
    df.dropna(subset=["russia_dependency"])
    .groupby("country_code")["russia_dependency"]
    .first()
    .sort_values(ascending=False)
)

fig, ax = plt.subplots(figsize=(10, 5))
bars = ax.bar(country_dep.index, country_dep.values, color="steelblue", edgecolor="white")

ax.set_xlabel("Country")
ax.set_ylabel("Russian Gas Dependency")
ax.set_title("Russian Gas Dependency by Country")
ax.tick_params(axis="x", rotation=45)

for bar, val in zip(bars, country_dep.values):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 0.02,
        f"{val:.2f}",
        ha="center",
        va="bottom",
        fontsize=8,
    )

plt.tight_layout()
plt.savefig(os.path.join(OUTPUTS_DIR, 'panel', 'others', 'russian_gas_dependence.png'), dpi=150)
plt.show()
