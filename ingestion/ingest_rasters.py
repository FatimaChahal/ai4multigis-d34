import rasterio
from rasterio.warp import transform_bounds
from shapely.geometry import box
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

engine = create_engine(
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Test connection
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("Database connection OK")
except Exception as e:
    print(f"Database connection FAILED: {e}")
    exit(1)

def ingest_raster_metadata(tif_path: Path, layer_name: str):
    print(f"  Loading {tif_path.name} ...")
    try:
        with rasterio.open(tif_path) as src:
            crs = str(src.crs)
            resolution = src.res[0]
            bounds = src.bounds
            band_count = src.count
            left, bottom, right, top = transform_bounds(
                src.crs, "EPSG:4326",
                bounds.left, bounds.bottom,
                bounds.right, bounds.top
            )
            bbox_wkt = box(left, bottom, right, top).wkt

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO raw_data.raster_metadata
                    (layer_name, source, file_path, resolution, crs, bbox)
                VALUES
                    (:layer_name, :source, :file_path, :resolution, :crs,
                     ST_GeomFromText(:bbox_wkt, 4326))
            """), {
                "layer_name": layer_name,
                "source": tif_path.parent.name,
                "file_path": str(tif_path),
                "resolution": resolution,
                "crs": crs,
                "bbox_wkt": bbox_wkt
            })

        print(f"    OK: {crs}, {band_count} bands, {resolution:.4f} res")
        return 1

    except Exception as e:
        print(f"    ERROR: {e}")
        return 0


def ingest_all_rasters():
    rasters_root = Path("/home/fatima/D3.4/data/rasters")
    total = 0

    raster_datasets = {
        "Landuse": "landuse",
        "SatImg": "sentinel2",
        "DEM": "dem",
    }

    for folder_name, layer_name in raster_datasets.items():
        folder_path = rasters_root / folder_name
        if not folder_path.exists():
            print(f"SKIP: {folder_path} not found")
            continue

        tif_files = list(folder_path.glob("*.tif"))
        print(f"\n=== {folder_name}: {len(tif_files)} rasters ===")

        for tif_path in sorted(tif_files):
            sublayer = f"{layer_name}/{tif_path.stem}"
            count = ingest_raster_metadata(tif_path, sublayer)
            total += count

    print(f"\nTOTAL rasters ingested: {total}")


if __name__ == "__main__":
    print("Starting raster ingestion...")
    ingest_all_rasters()
    print("Done.")