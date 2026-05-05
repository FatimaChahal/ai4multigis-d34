import geopandas as gpd
import numpy as np
from shapely.geometry import box
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import json

load_dotenv("/home/fatima/D3.4/config/.env")

engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

# Chelmsford AOI bounding box (WGS84)
AOI_WEST  = 0.328
AOI_EAST  = 0.658
AOI_SOUTH = 51.616
AOI_NORTH = 51.863

# Grid cell size in degrees (~500m at this latitude)
CELL_SIZE = 0.005

def create_grid():
    """Create a regular grid over the Chelmsford AOI."""
    print("Creating spatial grid...")
    
    x_coords = np.arange(AOI_WEST, AOI_EAST, CELL_SIZE)
    y_coords = np.arange(AOI_SOUTH, AOI_NORTH, CELL_SIZE)
    
    cells = []
    for x in x_coords:
        for y in y_coords:
            cell = box(x, y, x + CELL_SIZE, y + CELL_SIZE)
            cells.append(cell)
    
    print(f"  Grid created: {len(cells)} cells "
          f"({len(x_coords)} cols x {len(y_coords)} rows)")
    return cells


def compute_feature_vector(cell_wkt: str, conn) -> dict:
    """
    For a given grid cell, compute spatial features by overlaying
    all vector layers. Returns a feature vector dict.
    """
    features = {}

    # Risk band mapping: text -> numeric score
    # Used in SQL CASE statements
    risk_case = """
        MAX(CASE properties->>'risk_band'
            WHEN 'High'     THEN 4
            WHEN 'Medium'   THEN 3
            WHEN 'Low'      THEN 2
            WHEN 'Very low' THEN 1
            ELSE 0
        END)
    """

    # Feature 1: Flood risk from rivers & sea
    result = conn.execute(text(f"""
        SELECT {risk_case}
        FROM raw_data.vector_layers
        WHERE split_part(layer_name, '/', 1) = 'risk_flooding_rivers_sea'
        AND ST_Intersects(geom, ST_GeomFromText(:cell, 4326))
    """), {"cell": cell_wkt})
    val = result.scalar()
    features["flood_risk_rivers_sea"] = int(val) if val else 0

    # Feature 2: Flood risk from surface water
    result = conn.execute(text(f"""
        SELECT {risk_case}
        FROM raw_data.vector_layers
        WHERE split_part(layer_name, '/', 1) = 'risk_flooding_surface_water'
        AND ST_Intersects(geom, ST_GeomFromText(:cell, 4326))
    """), {"cell": cell_wkt})
    val = result.scalar()
    features["flood_risk_surface_water"] = int(val) if val else 0

    # Feature 3: Flood risk climate change scenario
    result = conn.execute(text(f"""
        SELECT {risk_case}
        FROM raw_data.vector_layers
        WHERE split_part(layer_name, '/', 1) = 'risk_flooding_surface_water_cc1'
        AND ST_Intersects(geom, ST_GeomFromText(:cell, 4326))
    """), {"cell": cell_wkt})
    val = result.scalar()
    features["flood_risk_climate_change"] = int(val) if val else 0

    # Feature 4: River presence
    result = conn.execute(text("""
        SELECT COUNT(*)
        FROM raw_data.vector_layers
        WHERE split_part(layer_name, '/', 1) = 'os_open_rivers'
        AND ST_Intersects(geom, ST_GeomFromText(:cell, 4326))
    """), {"cell": cell_wkt})
    features["river_presence"] = 1 if result.scalar() > 0 else 0

    # Feature 5: Road density
    result = conn.execute(text("""
        SELECT COUNT(*)
        FROM raw_data.vector_layers
        WHERE split_part(layer_name, '/', 1) = 'road_network'
        AND layer_name LIKE '%RoadLink%'
        AND ST_Intersects(geom, ST_GeomFromText(:cell, 4326))
    """), {"cell": cell_wkt})
    features["road_density"] = int(result.scalar())

    # Feature 6: Combined risk score (weighted sum)
    features["composite_risk_score"] = round(
        features["flood_risk_rivers_sea"] * 0.4 +
        features["flood_risk_surface_water"] * 0.35 +
        features["flood_risk_climate_change"] * 0.25,
        3
    )

    return features


def build_master_grid():
    """Build the MASTER_GRID analytical index."""
    
    # Step 1: Create grid cells
    cells = create_grid()
    total = len(cells)

    # Step 2: Clear existing grid
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE processed_data.master_grid"))
    print("Cleared existing master_grid")

    # Step 3: For each cell compute features and insert
    print(f"\nProcessing {total} cells...")
    inserted = 0
    skipped = 0

    with engine.begin() as conn:
        for i, cell in enumerate(cells):
            cell_wkt = cell.wkt

            # Compute feature vector
            features = compute_feature_vector(cell_wkt, conn)

            # Only insert cells that have at least one non-zero feature
            # This keeps the index focused on the actual AOI data
            if all(v == 0 for v in features.values()):
                skipped += 1
            else:
                conn.execute(text("""
                    INSERT INTO processed_data.master_grid
                        (geom, feature_vector, index_version)
                    VALUES
                        (ST_GeomFromText(:geom, 4326),
                         CAST(:features AS jsonb),
                         1)
                """), {
                    "geom": cell_wkt,
                    "features": json.dumps(features)
                })
                inserted += 1

            # Progress update every 100 cells
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i+1}/{total} cells "
                      f"({inserted} inserted, {skipped} empty)")

    print(f"\nMASTER_GRID complete!")
    print(f"  Total cells processed : {total}")
    print(f"  Cells with data       : {inserted}")
    print(f"  Empty cells skipped   : {skipped}")


def verify_grid():
    """Print a summary of the master grid."""
    print("\nVerifying MASTER_GRID...")
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                COUNT(*) as total_cells,
                AVG((feature_vector->>'flood_risk_rivers_sea')::float) 
                    as avg_flood_risk_rivers,
                AVG((feature_vector->>'flood_risk_surface_water')::float) 
                    as avg_flood_risk_surface,
                SUM((feature_vector->>'river_presence')::int) 
                    as cells_with_rivers,
                AVG((feature_vector->>'road_density')::float) 
                    as avg_road_density
            FROM processed_data.master_grid
        """))
        row = result.fetchone()
        print(f"  Total cells          : {row[0]}")
        print(f"  Avg flood risk (R&S) : {row[1]:.3f}" if row[1] else 
              "  Avg flood risk (R&S) : 0.000")
        print(f"  Avg flood risk (SW)  : {row[2]:.3f}" if row[2] else
              "  Avg flood risk (SW)  : 0.000")
        print(f"  Cells with rivers    : {row[3]}")
        print(f"  Avg road density     : {row[4]:.2f}" if row[4] else
              "  Avg road density     : 0.00")


if __name__ == "__main__":
    print("Starting MASTER_GRID construction...")
    build_master_grid()
    verify_grid()
    print("\nDone.")