-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;

-- Schemas
CREATE SCHEMA IF NOT EXISTS raw_data;
CREATE SCHEMA IF NOT EXISTS processed_data;
CREATE SCHEMA IF NOT EXISTS governance;

-- Generic vector table
CREATE TABLE raw_data.vector_layers (
    id          SERIAL PRIMARY KEY,
    layer_name  TEXT NOT NULL,
    source      TEXT,
    geom        GEOMETRY,
    properties  JSONB,
    ingested_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_vector_geom 
    ON raw_data.vector_layers 
    USING GIST (geom);

-- Raster metadata table
CREATE TABLE raw_data.raster_metadata (
    id          SERIAL PRIMARY KEY,
    layer_name  TEXT NOT NULL,
    source      TEXT,
    file_path   TEXT,
    resolution  FLOAT,
    crs         TEXT,
    bbox        GEOMETRY,
    ingested_at TIMESTAMP DEFAULT NOW()
);

-- Tabular/Excel data table
CREATE TABLE raw_data.tabular_data (
    id          SERIAL PRIMARY KEY,
    source_file TEXT,
    layer_name  TEXT,
    properties  JSONB,
    ingested_at TIMESTAMP DEFAULT NOW()
);

-- Master grid index
CREATE TABLE processed_data.master_grid (
    cell_id         SERIAL PRIMARY KEY,
    geom            GEOMETRY(Polygon, 4326),
    feature_vector  JSONB,
    index_version   INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_master_grid_geom 
    ON processed_data.master_grid 
    USING GIST (geom);

-- Provenance log
CREATE TABLE governance.provenance_log (
    id              SERIAL PRIMARY KEY,
    event_type      TEXT NOT NULL,
    layer_name      TEXT,
    actor           TEXT,
    index_version   INTEGER,
    data_hash       TEXT,
    blockchain_tx   TEXT,
    timestamp       TIMESTAMP DEFAULT NOW(),
    metadata        JSONB
);
