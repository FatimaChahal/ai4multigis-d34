#!/usr/bin/env python3
"""
main_with_blockchain.py — D3.4 AI4MultiGIS
Full end-to-end pipeline: PostGIS data ingestion → MASTER_GRID build
→ SHA-256 hash → Besu QBFT registration → on-chain provenance logging.
"""

import sys, json, hashlib, logging
from datetime import datetime
from sqlalchemy import text

# ── Pipeline imports ──────────────────────────────────────────────────────────
sys.path.insert(0, "/home/fatima/D3.4")
from pipeline.build_master_grid import build_master_grid, verify_grid, engine

# ── Blockchain imports ────────────────────────────────────────────────────────
sys.path.insert(0, "/home/fatima/D3.4/blockchain")
from ledger_interface import (
    register_index_version,
    validate_index_version,
    verify_index_hash,
    log_operation,
    get_provenance_entry,
    compute_gis_hash,
    w3, cfg
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("Pipeline")


def fetch_master_grid_snapshot() -> list:
    """Fetch all MASTER_GRID rows for deterministic hashing."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT cell_id,
                   ST_AsText(geom)   AS geom_wkt,
                   feature_vector,
                   index_version,
                   created_at
            FROM processed_data.master_grid
            ORDER BY cell_id
        """))
        return [list(r) for r in result.fetchall()]


def compute_master_grid_hash(rows: list) -> str:
    """Compute deterministic SHA-256 over the full MASTER_GRID snapshot."""
    serialised = json.dumps(rows, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def update_provenance_log(tx_hash: str, layer_name: str, data_hash: str):
    """Write the real TX hash back to the PostGIS provenance log."""
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE governance.provenance_log
                SET blockchain_tx = :tx_hash
                WHERE layer_name  = :layer
                AND   data_hash   = :data_hash
            """), {
                "tx_hash":   tx_hash,
                "layer":     layer_name,
                "data_hash": data_hash,
            })
        log.info("Provenance log updated with TX hash")
    except Exception as e:
        log.warning(f"Could not update provenance log: {e}")


def run_full_pipeline():
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info(f"=== AI4MultiGIS D3.4 Pipeline — Run {run_id} ===")

    # ── Step 1: Check blockchain connectivity ─────────────────────────────────
    log.info("[1/7] Checking Besu QBFT connectivity...")
    if not w3.is_connected():
        raise ConnectionError("Besu node not reachable at http://127.0.0.1:8545")
    log.info(f"      Connected — block #{w3.eth.block_number}")

    # ── Step 2: Build MASTER_GRID in PostGIS ──────────────────────────────────
    log.info("[2/7] Building MASTER_GRID in PostGIS...")
    build_master_grid()
    verify_grid()

    # ── Step 3: Fetch snapshot and compute hash ───────────────────────────────
    log.info("[3/7] Computing SHA-256 hash of MASTER_GRID...")
    rows = fetch_master_grid_snapshot()
    if not rows:
        raise ValueError("MASTER_GRID is empty — cannot register empty dataset")
    data_hash = compute_master_grid_hash(rows)
    log.info(f"      {len(rows)} cells hashed → {data_hash[:32]}...")

    layer_name   = "MASTER_GRID_v1"
    actor        = "fatima@UPPA"
    metadata_ref = f"PostGIS:processed_data.master_grid:run={run_id}"

    # ── Step 4: Log INGEST operation on-chain ────────────────────────────────
    log.info("[4/7] Logging INGEST operation to ProvenanceLogger...")
    ingest_result = log_operation(
        operation    = "INGEST",
        input_hash   = "RAW_GIS_DATA",
        output_hash  = data_hash,
        actor        = actor,
        metadata_ref = metadata_ref,
    )
    log.info(f"      Entry ID : {ingest_result['entry_id']}")
    log.info(f"      TX hash  : {ingest_result['tx_hash']}")
    log.info(f"      Block    : {ingest_result['block_number']}")

    # ── Step 5: Register index version on GISIndexRegistry ───────────────────
    log.info("[5/7] Registering index version on GISIndexRegistry...")
    reg_result = register_index_version(
        data_hash    = data_hash,
        layer_name   = layer_name,
        actor        = actor,
        metadata_ref = metadata_ref,
    )
    log.info(f"      Version ID : {reg_result['version_id']}")
    log.info(f"      TX hash    : {reg_result['tx_hash']}")
    log.info(f"      Block      : {reg_result['block_number']}")
    log.info(f"      Gas used   : {reg_result['gas_used']}")
    log.info(f"      Status     : {reg_result['status']}")

    # ── Step 6: Validate index version ────────────────────────────────────────
    log.info("[6/7] Validating index version on-chain...")
    val_result = validate_index_version(reg_result["version_id"])
    log.info(f"      TX hash : {val_result['tx_hash']}")
    log.info(f"      Status  : {val_result['status']}")

    # ── Step 7: Verify and write back to PostGIS ──────────────────────────────
    log.info("[7/7] Verifying hash and updating PostGIS provenance log...")
    is_valid = verify_index_hash(reg_result["version_id"], data_hash)
    log.info(f"      Hash verified on-chain : {is_valid}")
    update_provenance_log(reg_result["tx_hash"], layer_name, data_hash)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  AI4MultiGIS D3.4 — Pipeline Complete")
    print("=" * 60)
    print(f"  Run ID            : {run_id}")
    print(f"  MASTER_GRID cells : {len(rows)}")
    print(f"  Data hash         : {data_hash[:32]}...")
    print(f"  GIS version ID    : {reg_result['version_id']}")
    print(f"  Register TX       : {reg_result['tx_hash']}")
    print(f"  Validate TX       : {val_result['tx_hash']}")
    print(f"  Block number      : {reg_result['block_number']}")
    print(f"  Hash verified     : {is_valid}")
    print(f"  Network           : Hyperledger Besu QBFT (chainId=1337)")
    print(f"  GISIndexRegistry  : {cfg['contractAddress']}")
    print(f"  ProvenanceLogger  : {cfg['provenanceLoggerAddress']}")
    print("=" * 60)

    return {
        "run_id":       run_id,
        "data_hash":    data_hash,
        "version_id":   reg_result["version_id"],
        "tx_hash":      reg_result["tx_hash"],
        "block_number": reg_result["block_number"],
        "verified":     is_valid,
    }


if __name__ == "__main__":
    result = run_full_pipeline()
    print("\nResult JSON:")
    print(json.dumps(result, indent=2))
