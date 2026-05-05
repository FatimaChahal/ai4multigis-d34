import geopandas as gpd
import json
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# Use absolute path for .env
load_dotenv("/home/fatima/D3.4/config/.env")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

print(f"Connecting to: {DB_HOST}:{DB_PORT}/{DB_NAME}")

engine = create_engine(
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Test connection immediately
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("Database connection OK")
except Exception as e:
    print(f"Database connection FAILED: {e}")
    exit(1)

TARGET_CRS = "EPSG:4326"

def ingest_shapefile(shp_path: Path, layer_name: str):
    print(f"  Loading {shp_path.name} ...")
    try:
        gdf = gpd.read_file(shp_path)
        print(f"    Read {len(gdf)} features, CRS: {gdf.crs}")

        if gdf.crs is None:
            print(f"    WARNING: No CRS, assuming EPSG:32630")
            gdf = gdf.set_crs("EPSG:32630")
        gdf = gdf.to_crs(TARGET_CRS)

        rows = []
        for _, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            props = {
                col: (str(val) if val is not None else None)
                for col, val in row.items()
                if col != "geometry"
            }
            rows.append({
                "layer_name": layer_name,
                "source": str(shp_path),
                "geom": geom.wkt,
                "properties": json.dumps(props)
            })

        if not rows:
            print(f"    SKIPPED: no valid geometries")
            return 0

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO raw_data.vector_layers
                    (layer_name, source, geom, properties)
                VALUES
                    (:layer_name, :source,
                    ST_GeomFromText(:geom, 4326),
                    CAST(:properties AS jsonb))
            """), rows)

        print(f"    OK: {len(rows)} features inserted")
        return len(rows)

    except Exception as e:
        print(f"    ERROR: {e}")
        return 0


def ingest_all_vectors():
    vectors_root = Path("/home/fatima/D3.4/data/vectors")
    total = 0

    vector_datasets = {
        "OS_Open_Rivers": "os_open_rivers",
        "Risk_Flooding_Rivers_Sea": "risk_flooding_rivers_sea",
        "Risk_Flooding_Surface_Water": "risk_flooding_surface_water",
        "Risk_Flooding_Surface_Water_CC1": "risk_flooding_surface_water_cc1",
        "Road_Network": "road_network",
    }

    for folder_name, layer_name in vector_datasets.items():
        folder_path = vectors_root / folder_name
        if not folder_path.exists():
            print(f"SKIP: {folder_path} not found")
            continue

        shp_files = list(folder_path.glob("*.shp"))
        print(f"\n=== {folder_name}: {len(shp_files)} shapefiles ===")

        for shp_path in sorted(shp_files):
            sublayer = f"{layer_name}/{shp_path.stem}"
            count = ingest_shapefile(shp_path, sublayer)
            total += count

    print(f"\nTOTAL features ingested: {total}")


if __name__ == "__main__":
    ingest_all_vectors()
    print("Done.")
