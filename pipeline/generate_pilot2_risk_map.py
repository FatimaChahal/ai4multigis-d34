"""
D3.4 Pilot 2 — Romanian AOI Risk Grid Map
Generates a QGIS-compatible GeoPackage with the preliminary
invasion risk grid, ready to style and export in QGIS.

Steps this script performs:
1. Loads WoC occurrences from PostGIS raw_data.woc_occurrences
2. Creates a 0.5-degree grid over the Romanian AOI (lat 40-50, lon 20-30)
3. For each cell computes:
   - total_count    : total occurrence records
   - alien_count    : alien species records
   - native_count   : native species records
   - species_rich   : unique species count
   - risk_score     : composite invasion risk (0-4 scale)
4. Saves the grid as:
   - GeoPackage (.gpkg) for QGIS styling
   - PostGIS table processed_data.romania_risk_grid
   - Summary CSV

Usage:
    python3 pipeline/generate_pilot2_risk_map.py

QGIS styling instructions are printed at the end of the run.
"""

import os, logging
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import box
from sqlalchemy import create_engine, text

load_dotenv("/home/fatima/D3.4/config/.env")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("Pilot2RiskGrid")

OUTPUT_DIR = Path("/home/fatima/D3.4/outputs/figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CELL_SIZE = 0.5
LON_MIN, LON_MAX = 20.0, 30.0
LAT_MIN, LAT_MAX = 40.0, 50.0
CRS = "EPSG:4326"

log.info("Connecting to PostGIS...")
engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

log.info("Loading WoC occurrences from PostGIS...")
with engine.connect() as conn:
    df = pd.read_sql(text("""
        SELECT
            woc_id,
            ST_X(geom)   AS longitude,
            ST_Y(geom)   AS latitude,
            species_name,
            status,
            year_of_record,
            accuracy
        FROM raw_data.woc_occurrences
        WHERE ST_Y(geom) BETWEEN :lat_min AND :lat_max
          AND ST_X(geom) BETWEEN :lon_min AND :lon_max
    """), conn, params={
        "lat_min": LAT_MIN, "lat_max": LAT_MAX,
        "lon_min": LON_MIN, "lon_max": LON_MAX
    })

log.info(f"Loaded {len(df)} records in Romanian AOI")
log.info(f"Status: {df['status'].value_counts().to_dict()}")
log.info(f"Species: {df['species_name'].nunique()} unique")

log.info(f"Building {CELL_SIZE} degree grid over Romanian AOI...")
lon_edges = np.arange(LON_MIN, LON_MAX + CELL_SIZE, CELL_SIZE)
lat_edges = np.arange(LAT_MIN, LAT_MAX + CELL_SIZE, CELL_SIZE)

cells = []
for i, lat in enumerate(lat_edges[:-1]):
    for j, lon in enumerate(lon_edges[:-1]):
        mask = (
            (df['longitude'] >= lon) &
            (df['longitude'] <  lon + CELL_SIZE) &
            (df['latitude']  >= lat) &
            (df['latitude']  <  lat + CELL_SIZE)
        )
        cell_df = df[mask]
        total   = len(cell_df)
        alien   = (cell_df['status'] == 'Alien').sum()
        native  = (cell_df['status'] == 'Native').sum()
        introd  = (cell_df['status'] == 'Introduced').sum()
        species = cell_df['species_name'].nunique() if total > 0 else 0
        dominant = (cell_df['species_name'].value_counts().index[0]
                    if total > 0 else None)

        if total == 0:
            risk = 0.0
        elif alien > 0:
            alien_ratio = alien / total
            risk = 2.0 + (alien_ratio * 2.0)
        else:
            risk = min(1.0 + (native / 20.0), 2.0)

        risk = round(min(risk, 4.0), 2)

        cells.append({
            'cell_id':      f"RO_{i:02d}_{j:02d}",
            'lon_min':      lon,
            'lat_min':      lat,
            'total_count':  int(total),
            'alien_count':  int(alien),
            'native_count': int(native),
            'introd_count': int(introd),
            'species_rich': int(species),
            'dominant_sp':  dominant,
            'risk_score':   risk,
            'risk_class':   (
                'Absent'    if total == 0 else
                'Low'       if risk < 1.5 else
                'Moderate'  if risk < 2.5 else
                'High'      if risk < 3.5 else
                'Very High'
            ),
            'geometry': box(lon, lat, lon + CELL_SIZE, lat + CELL_SIZE)
        })

grid_gdf = gpd.GeoDataFrame(cells, geometry='geometry', crs=CRS)
occupied  = grid_gdf[grid_gdf['total_count'] > 0]
log.info(f"Grid: {len(grid_gdf)} total cells | {len(occupied)} occupied")

# Save GeoPackage
gpkg_path = OUTPUT_DIR / 'Pilot2_Romania_RiskGrid.gpkg'
grid_gdf.to_file(gpkg_path, driver='GPKG', layer='romania_risk_grid')

# Add occurrence points as second layer
points_gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df['longitude'], df['latitude']),
    crs=CRS
)
points_gdf.to_file(gpkg_path, driver='GPKG', layer='woc_occurrences', mode='a')
log.info(f"GeoPackage saved: {gpkg_path}")

# Save to PostGIS
try:
    grid_gdf.to_postgis('romania_risk_grid', engine,
                         schema='processed_data', if_exists='replace',
                         index=False)
    log.info("Saved to processed_data.romania_risk_grid in PostGIS")
except Exception as e:
    log.warning(f"PostGIS save skipped: {e}")

# Save summary CSV
csv_path = OUTPUT_DIR / 'Pilot2_Romania_RiskGrid_Summary.csv'
grid_gdf[grid_gdf['total_count'] > 0][[
    'cell_id','lon_min','lat_min','total_count','alien_count',
    'native_count','species_rich','dominant_sp','risk_score','risk_class'
]].sort_values('risk_score', ascending=False).to_csv(csv_path, index=False)
log.info(f"CSV saved: {csv_path}")

print("\n" + "="*65)
print("  Pilot 2 Risk Grid — QGIS Styling Instructions")
print("="*65)
print(f"\n  GeoPackage: {gpkg_path}")
print(f"  Layer 1: romania_risk_grid  (grid cells with risk scores)")
print(f"  Layer 2: woc_occurrences    (occurrence points)")
print(f"""
  QGIS Steps:
  1. Open QGIS
     Layer → Add Layer → Add Vector Layer
     Select: {gpkg_path}
     Add BOTH layers

  2. Add OpenStreetMap basemap:
     Browser panel → XYZ Tiles → OpenStreetMap → drag to map

  3. Style the risk grid layer:
     Right-click → Properties → Symbology
     → Graduated → Column: risk_score
     → Mode: Equal Interval → Classes: 5
     → Color ramp (manual):
        0.0 = #F5F5DC  (cream  / absent)
        1.5 = #F5E642  (yellow / low)
        2.5 = #F5A623  (orange / moderate)
        3.5 = #E24B4A  (red    / high)
        4.0 = #8B0000  (dark red / very high)
     → Opacity: 75%
     → Border: white, 0.2

  4. Style the occurrence points:
     → Categorized → Column: status
        Alien      = #E24B4A  size 3.0
        Native     = #0F6E56  size 3.0
        Introduced = #854F0B  size 3.0

  5. Export:
     Project → Import/Export → Export Map to Image
     Resolution: 200 dpi
     Save as: Pilot2_Fig4_RiskGrid_QGIS.png
""")

print("  Risk class distribution:")
print(f"  {'Class':<12} {'Cells':>6} {'%':>6}")
print(f"  {'-'*26}")
for cls in ['Very High','High','Moderate','Low','Absent']:
    cnt = (grid_gdf['risk_class'] == cls).sum()
    pct = cnt / len(grid_gdf) * 100
    print(f"  {cls:<12} {cnt:>6} {pct:>5.1f}%")
print("="*65)
print("\n=== Script complete ===\n")
