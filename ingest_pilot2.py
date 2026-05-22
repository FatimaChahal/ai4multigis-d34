import os
from dotenv import load_dotenv
load_dotenv("/home/fatima/D3.4/config/.env")
import geopandas as gpd
from sqlalchemy import create_engine

engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

files = {
    "pilot2_contours": "/home/fatima/D3.4/data/contours-romania.geojson",
    "pilot2_rivers":   "/home/fatima/D3.4/data/rivers-romania.geojson",
    "pilot2_master_grid": "/home/fatima/D3.4/data/master_grid.geojson",
}

for table_name, filepath in files.items():
    print(f"Loading {filepath} → {table_name} ...")
    gdf = gpd.read_file(filepath)
    gdf = gdf.to_crs("EPSG:4326")
    gdf.to_postgis(table_name, engine, if_exists="replace", index=False)
    print(f"  OK: {len(gdf)} features inserted")

print("Done!")
