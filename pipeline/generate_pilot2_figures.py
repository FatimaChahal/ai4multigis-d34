"""
D3.4 Pilot 2 — Figure Generation Script
Generates three publication-ready PNG figures for Section 7.2:
  Fig 1: European species distribution map
  Fig 2: Romanian AOI zoom map  
  Fig 3: Species/status bar chart
Data source: raw_data.woc_occurrences (PostGIS)
Output: /home/fatima/D3.4/outputs/figures/
"""
import os, json, logging
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
from sqlalchemy import create_engine, text

load_dotenv("/home/fatima/D3.4/config/.env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger("Pilot2Figures")

# ── CONFIG ────────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("/home/fatima/D3.4/outputs/figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

STATUS_COLORS = {
    'Alien':         '#E24B4A',
    'Native':        '#0F6E56',
    'Introduced':    '#854F0B',
    'Type locality': '#534AB7'
}

plt.rcParams.update({
    'font.family':        'DejaVu Sans',
    'axes.spines.top':    False,
    'axes.spines.right':  False,
})

LAND_COLOR  = '#EAE6DC'
OCEAN_COLOR = '#C8DCF0'

# ── LOAD DATA FROM POSTGIS ────────────────────────────────────────────────────
log.info("Loading WoC data from PostGIS...")
with engine.connect() as conn:
    df = pd.read_sql(text("""
        SELECT woc_id,
               ST_X(geom) AS longitude,
               ST_Y(geom) AS latitude,
               species_name,
               status,
               year_of_record,
               accuracy,
               contributor
        FROM raw_data.woc_occurrences
        ORDER BY woc_id
    """), conn)

log.info(f"Loaded {len(df)} records from PostGIS")
log.info(f"Status distribution: {df['status'].value_counts().to_dict()}")

# European subset
europe = df[(df['latitude'] >= 35) & (df['latitude'] <= 72) &
            (df['longitude'] >= -15) & (df['longitude'] <= 45)]
other  = df[~df.index.isin(europe.index)]

# Romanian AOI subset
romania = df[(df['latitude'] >= 40) & (df['latitude'] <= 50) &
             (df['longitude'] >= 20) & (df['longitude'] <= 30)]

log.info(f"European records: {len(europe)} | Romanian AOI: {len(romania)}")

plot_order = ['Native', 'Introduced', 'Alien', 'Type locality']

# ─────────────────────────────────────────────────────────────────────────────
# FIGURE 1: EUROPEAN SPECIES DISTRIBUTION MAP
# ─────────────────────────────────────────────────────────────────────────────
log.info("Generating Figure 1 — European distribution map...")
fig1, ax1 = plt.subplots(figsize=(14, 9))
fig1.patch.set_facecolor('#F7F8FA')
ax1.set_facecolor(OCEAN_COLOR)

# Land background polygons
europe_land = plt.Polygon([
    (-10,35),(-10,60),(-5,60),(-5,65),(5,65),(5,70),(15,70),(15,75),
    (30,75),(30,70),(40,70),(40,65),(45,65),(45,35),(-10,35)
], closed=True, facecolor=LAND_COLOR, edgecolor='#AAAAAA', linewidth=0.5, zorder=1)
ax1.add_patch(europe_land)

scandinavia = plt.Polygon([
    (5,57),(5,65),(10,70),(15,71),(20,70),(25,70),(30,65),(28,57),
    (20,55),(15,56),(5,57)
], closed=True, facecolor=LAND_COLOR, edgecolor='#AAAAAA', linewidth=0.5, zorder=2)
ax1.add_patch(scandinavia)

britain = plt.Polygon([
    (-5,50),(-5,58),(-3,59),(0,58),(0,51),(-5,50)
], closed=True, facecolor=LAND_COLOR, edgecolor='#AAAAAA', linewidth=0.5, zorder=2)
ax1.add_patch(britain)

# Plot occurrences by status
for status in plot_order:
    subset = europe[europe['status'] == status]
    color  = STATUS_COLORS.get(status, '#888780')
    if len(subset) > 0:
        ax1.scatter(subset['longitude'], subset['latitude'],
                   c=color, s=22, alpha=0.82,
                   linewidths=0.4, edgecolors='white',
                   zorder=5, label=f"{status} (n={len(subset)})")

# Romanian AOI box
romania_box = Rectangle((20, 40), 10, 10,
                         linewidth=2.2, edgecolor='#185FA5',
                         facecolor='#185FA5', alpha=0.08,
                         linestyle='--', zorder=8)
ax1.add_patch(romania_box)
ax1.text(25, 50.7,
         f'Romanian AOI\n({len(romania)} records · planned MASTER_GRID)',
         ha='center', va='bottom', fontsize=8.5, color='#185FA5',
         fontweight='bold',
         bbox=dict(boxstyle='round,pad=0.35', facecolor='white',
                   edgecolor='#185FA5', alpha=0.95, linewidth=1.2))

ax1.set_xlim(-15, 45)
ax1.set_ylim(35, 72)
ax1.grid(True, alpha=0.25, linestyle='--', color='#888780', linewidth=0.7, zorder=3)
ax1.set_xlabel('Longitude (°E)', fontsize=11, color='#2C2C2A', labelpad=8)
ax1.set_ylabel('Latitude (°N)', fontsize=11, color='#2C2C2A', labelpad=8)
ax1.set_title(
    'World of Crayfish (WoC v1.2) — European Occurrence Distribution\n'
    f'Pilot 2 · AI4MultiGIS D3.4 · {len(europe):,} records shown · 21 species',
    fontsize=13, fontweight='bold', color='#1A2340', pad=14
)
legend1 = ax1.legend(title='Conservation status', title_fontsize=10,
                     fontsize=9.5, loc='upper left',
                     framealpha=0.96, edgecolor='#CCCCCC', fancybox=True)
ax1.text(44, 35.8,
         f'{len(other)} records outside European extent not shown\n'
         f'(North American, Asian, and southern hemisphere records)',
         ha='right', va='bottom', fontsize=8, color='#888780', style='italic')
ax1.text(-14, 35.5,
         'Source: World of Crayfish (WoC) database v1.2 · AI4MultiGIS D3.4 · raw_data.woc_occurrences (PostGIS)',
         fontsize=7.5, color='#888780', style='italic')

plt.tight_layout()
out1 = OUTPUT_DIR / 'Pilot2_Fig1_EuropeMap.png'
fig1.savefig(out1, dpi=200, bbox_inches='tight', facecolor='#F7F8FA')
plt.close()
log.info(f"Figure 1 saved: {out1}")

# ─────────────────────────────────────────────────────────────────────────────
# FIGURE 2: ROMANIAN AOI ZOOM
# ─────────────────────────────────────────────────────────────────────────────
log.info("Generating Figure 2 — Romanian AOI zoom...")
fig2, ax2 = plt.subplots(figsize=(12, 8))
fig2.patch.set_facecolor('#F7F8FA')
ax2.set_facecolor('#EAE6DC')

# Approximate Romania outline
romania_outline = plt.Polygon([
    (22.0,47.8),(22.5,48.2),(23.5,48.4),(24.5,48.2),(26.0,48.0),
    (27.0,47.5),(29.5,45.5),(29.8,45.2),(29.5,44.5),(28.5,43.8),
    (27.5,43.8),(26.5,44.2),(25.5,43.8),(24.0,43.7),(22.5,44.0),
    (21.0,44.5),(20.5,45.5),(20.2,46.0),(20.5,47.0),(22.0,47.8)
], closed=True, facecolor='#EAF3DE', edgecolor='#3B6D11',
   linewidth=1.5, zorder=1, alpha=0.6)
ax2.add_patch(romania_outline)

for status in plot_order:
    subset = romania[romania['status'] == status]
    color  = STATUS_COLORS.get(status, '#888780')
    if len(subset) > 0:
        ax2.scatter(subset['longitude'], subset['latitude'],
                   c=color, s=65, alpha=0.85,
                   linewidths=0.6, edgecolors='white',
                   zorder=5, label=f"{status} (n={len(subset)})")

# Danube river approximation
danube_x = [20.2,21.5,22.5,23.5,25.0,26.5,27.5,28.5,29.5,29.8]
danube_y = [45.5,45.5,45.7,45.6,45.5,45.2,45.0,45.1,45.3,45.2]
ax2.plot(danube_x, danube_y, color='#185FA5', linewidth=1.5,
         alpha=0.5, zorder=3)
ax2.text(25.0, 45.0, 'Danube', fontsize=7.5,
         color='#185FA5', style='italic', alpha=0.8)
ax2.text(24.5, 47.2, 'Carpathians', fontsize=8,
         color='#5F5E5A', style='italic', alpha=0.8, rotation=-15)

# AOI bounding box
aoi_box = Rectangle((20, 40), 10, 10,
                     linewidth=2, edgecolor='#185FA5',
                     facecolor='none', linestyle='--', zorder=8)
ax2.add_patch(aoi_box)

ax2.set_xlim(19.8, 30.2)
ax2.set_ylim(39.5, 50.5)
ax2.grid(True, alpha=0.3, linestyle='--', color='#888780', linewidth=0.7)
ax2.set_xlabel('Longitude (°E)', fontsize=11, color='#2C2C2A', labelpad=8)
ax2.set_ylabel('Latitude (°N)', fontsize=11, color='#2C2C2A', labelpad=8)
ax2.set_title(
    'World of Crayfish — Romanian Area of Interest (AOI)\n'
    f'Pilot 2 · AI4MultiGIS D3.4 · {len(romania)} records · Planned MASTER_GRID extent',
    fontsize=13, fontweight='bold', color='#1A2340', pad=14
)

legend2 = ax2.legend(title='Conservation status', title_fontsize=10,
                     fontsize=9.5, loc='lower left',
                     framealpha=0.96, edgecolor='#CCCCCC', fancybox=True)

# Species breakdown inset
species_text = "Species in AOI:\n"
for sp, cnt in romania['species_name'].value_counts().items():
    parts = sp.split()
    short = f"{parts[0][0]}. {' '.join(parts[1:])}"
    species_text += f"  {short}: {cnt}\n"
ax2.text(29.9, 50.2, species_text.strip(),
         ha='right', va='top', fontsize=8, color='#2C2C2A',
         bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                   edgecolor='#CCCCCC', alpha=0.95))

ax2.text(20.0, 39.65,
         'Source: WoC v1.2 · AI4MultiGIS D3.4 · raw_data.woc_occurrences (PostGIS) · Romanian boundary approximate',
         fontsize=7.5, color='#888780', style='italic')

plt.tight_layout()
out2 = OUTPUT_DIR / 'Pilot2_Fig2_RomanianAOI.png'
fig2.savefig(out2, dpi=200, bbox_inches='tight', facecolor='#F7F8FA')
plt.close()
log.info(f"Figure 2 saved: {out2}")

# ─────────────────────────────────────────────────────────────────────────────
# FIGURE 3: SPECIES / STATUS BAR CHART
# ─────────────────────────────────────────────────────────────────────────────
log.info("Generating Figure 3 — Species/status bar chart...")

top_species = df['species_name'].value_counts().head(12).index.tolist()
df_top = df[df['species_name'].isin(top_species)]
pivot = df_top.groupby(['species_name','status']).size().unstack(fill_value=0)
for col in ['Native','Introduced','Alien']:
    if col not in pivot.columns:
        pivot[col] = 0
pivot = pivot[['Native','Introduced','Alien']]
pivot['total'] = pivot.sum(axis=1)
pivot = pivot.sort_values('total', ascending=True).drop(columns='total')

def shorten(name):
    parts = name.split()
    return f"{parts[0][0]}. {' '.join(parts[1:])}"

pivot.index = [shorten(s) for s in pivot.index]

fig3, ax3 = plt.subplots(figsize=(13, 8))
fig3.patch.set_facecolor('#F7F8FA')
ax3.set_facecolor('#F7F8FA')

colors = [STATUS_COLORS['Native'], STATUS_COLORS['Introduced'], STATUS_COLORS['Alien']]
pivot.plot(kind='barh', stacked=True, ax=ax3,
           color=colors, edgecolor='white', linewidth=0.5)

for i, (idx, row) in enumerate(pivot.iterrows()):
    total = row.sum()
    ax3.text(total + 2, i, f'{int(total)}',
             va='center', ha='left', fontsize=9,
             color='#2C2C2A', fontweight='bold')

ax3.set_xlabel('Number of occurrence records', fontsize=11,
               color='#2C2C2A', labelpad=8)
ax3.set_ylabel('')
ax3.set_title(
    'World of Crayfish (WoC v1.2) — Top 12 Species by Record Count\n'
    'Pilot 2 · AI4MultiGIS D3.4 · Stacked by conservation status',
    fontsize=13, fontweight='bold', color='#1A2340', pad=14
)
ax3.spines['top'].set_visible(False)
ax3.spines['right'].set_visible(False)
ax3.spines['left'].set_color('#CCCCCC')
ax3.spines['bottom'].set_color('#CCCCCC')
ax3.grid(axis='x', alpha=0.3, linestyle='--', color='#888780', linewidth=0.7)
ax3.set_xlim(0, pivot.sum(axis=1).max() * 1.15)

handles = [mpatches.Patch(color=STATUS_COLORS[s], label=s)
           for s in ['Native','Introduced','Alien']]
ax3.legend(handles=handles, title='Conservation status',
           title_fontsize=10, fontsize=9.5, loc='lower right',
           framealpha=0.96, edgecolor='#CCCCCC', fancybox=True)

# Annotation for top invasive species
top_row = len(pivot) - 1
top_total = pivot.iloc[top_row].sum()
ax3.annotate('Primary invasive\nspecies of concern\nin Central Europe',
             xy=(top_total, top_row),
             xytext=(top_total * 0.55, top_row - 1.5),
             fontsize=8, color='#A32D2D', style='italic',
             arrowprops=dict(arrowstyle='->', color='#A32D2D', lw=1.2),
             bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                       edgecolor='#E24B4A', alpha=0.9))

ax3.text(0, -1.2,
         'Source: World of Crayfish (WoC) database v1.2 · AI4MultiGIS D3.4 · raw_data.woc_occurrences (PostGIS)',
         fontsize=7.5, color='#888780', style='italic')

plt.tight_layout()
out3 = OUTPUT_DIR / 'Pilot2_Fig3_SpeciesChart.png'
fig3.savefig(out3, dpi=200, bbox_inches='tight', facecolor='#F7F8FA')
plt.close()
log.info(f"Figure 3 saved: {out3}")

print("\n" + "="*55)
print("  Pilot 2 figures generation complete!")
print("="*55)
print(f"  Fig 1 (Europe map)   : {out1}")
print(f"  Fig 2 (Romanian AOI) : {out2}")
print(f"  Fig 3 (Species chart): {out3}")
print("="*55 + "\n")
