"""
LedgerInterface — D3.4 AI4MultiGIS
Instrumented version with TimingProfiler for Section 6.2 performance measurements.

Measures four key operations:
  1. SHA-256 hash computation over the MASTER_GRID index
  2. TX submission to GISIndexRegistry smart contract
  3. TX confirmation (wait_for_transaction_receipt)
  4. Provenance log write-back to PostGIS

Run three times and collect the JSON reports for Section 6.2.
"""

import json
import os
import time
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

from web3 import Web3
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv("/home/fatima/D3.4/config/.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("LedgerInterface")


# ── TIMING PROFILER ───────────────────────────────────────────────────────────

@dataclass
class TimingRecord:
    """Stores a single timed measurement."""
    operation: str
    duration_s: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""


@dataclass
class TimingReport:
    """Aggregates all timing records for one full pipeline run."""
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    records: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add(self, operation: str, duration_s: float, notes: str = ""):
        self.records.append(TimingRecord(
            operation=operation,
            duration_s=round(duration_s, 4),
            notes=notes
        ))

    def total(self) -> float:
        return round(sum(r.duration_s for r in self.records), 4)

    def print_summary(self):
        print("\n" + "=" * 52)
        print("  D3.4 Performance Profile — LedgerInterface")
        print("=" * 52)
        for r in self.records:
            label = f"  {r.operation:<32}"
            print(f"{label}: {r.duration_s:.4f} s")
        print("-" * 52)
        print(f"  {'Total governance cycle':<32}: {self.total():.4f} s")
        print("=" * 52)

    def save(self, output_dir: str = "/home/fatima/D3.4/profiling"):
        """Save the report as a JSON file for later aggregation."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        filename = f"timing_report_{self.run_id}.json"
        filepath = Path(output_dir) / filename
        with open(filepath, "w") as f:
            json.dump({
                "run_id": self.run_id,
                "total_s": self.total(),
                "records": [asdict(r) for r in self.records],
                "metadata": self.metadata
            }, f, indent=2)
        log.info(f"Timing report saved: {filepath}")
        return str(filepath)


class Timer:
    """Simple context manager for measuring elapsed time."""
    def __init__(self):
        self.elapsed = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed = time.perf_counter() - self._start


# ── DATABASE AND BLOCKCHAIN SETUP ─────────────────────────────────────────────

engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

config_path = Path("/home/fatima/D3.4/config/contract_config.json")
with open(config_path) as f:
    contract_config = json.load(f)

CONTRACT_ADDRESS = contract_config["contractAddress"]
DEPLOYER_ADDRESS = contract_config["deployerAddress"]

abi_path = Path(
    "/home/fatima/D3.4/blockchain/artifacts/contracts/"
    "GISIndexRegistry.sol/GISIndexRegistry.json"
)
with open(abi_path) as f:
    artifact = json.load(f)
    CONTRACT_ABI = artifact["abi"]

contract = w3.eth.contract(
    address=CONTRACT_ADDRESS,
    abi=CONTRACT_ABI
)


# ── INSTRUMENTED FUNCTIONS ────────────────────────────────────────────────────

def compute_hash_from_db(report: TimingReport) -> str:
    """
    Stage 3 of the contribution workflow:
    Fetch the MASTER_GRID from PostGIS and compute its SHA-256 hash.
    Measures: hash computation time.
    """
    log.info("Fetching MASTER_GRID from PostGIS for hash computation...")

    # Fetch all grid cells (geometry + feature vector) from PostGIS
    with engine.connect() as conn:
        result = conn.execute(text("""
        SELECT cell_id,
               ST_AsText(geom) AS geom_wkt,
               feature_vector,
               index_version,
               created_at
        FROM processed_data.master_grid
        ORDER BY cell_id
    """))
        rows = result.fetchall()

    log.info(f"Fetched {len(rows)} grid cells for hashing.")

    # Serialise to a deterministic string and compute SHA-256
    with Timer() as t:
        serialised = json.dumps(
            [list(r) for r in rows],
            sort_keys=True,
            default=str
        )
        data_hash = hashlib.sha256(serialised.encode("utf-8")).hexdigest()

    report.add(
        operation="SHA-256 hash computation",
        duration_s=t.elapsed,
        notes=f"{len(rows)} grid cells serialised and hashed"
    )

    log.info(f"Hash computed in {t.elapsed:.4f}s : {data_hash[:32]}...")
    return data_hash


def register_index_version(
    data_hash: str,
    layer_name: str,
    actor: str,
    metadata_ref: str,
    provenance_log_id: int,
    report: TimingReport
) -> str:
    """
    Stage 4 of the contribution workflow:
    Submit hash to GISIndexRegistry and wait for confirmation.
    Measures: TX submission time and TX confirmation time separately.
    """
    log.info(f"Registering index version on blockchain...")
    log.info(f"  Layer : {layer_name}")
    log.info(f"  Actor : {actor}")
    log.info(f"  Hash  : {data_hash[:32]}...")

    if not w3.is_connected():
        raise ConnectionError("Cannot connect to blockchain node at http://127.0.0.1:8545")

    # ── Measure TX submission ─────────────────────────────────────────────────
    with Timer() as t_submit:
        tx_hash = contract.functions.registerIndexVersion(
            data_hash,
            layer_name,
            actor,
            metadata_ref
        ).transact({
            "from": DEPLOYER_ADDRESS,
            "gas": 500000
        })

    report.add(
        operation="TX submission to GISIndexRegistry",
        duration_s=t_submit.elapsed,
        notes="transact() call including signing"
    )
    log.info(f"TX submitted in {t_submit.elapsed:.4f}s")

    # ── Measure TX confirmation ───────────────────────────────────────────────
    with Timer() as t_confirm:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    report.add(
        operation="TX confirmation (block inclusion)",
        duration_s=t_confirm.elapsed,
        notes=f"Block #{receipt.blockNumber} · Gas used: {receipt.gasUsed}"
    )

    tx_hash_hex = receipt.transactionHash.hex()
    log.info(f"TX confirmed in {t_confirm.elapsed:.4f}s")
    log.info(f"  TX Hash  : {tx_hash_hex}")
    log.info(f"  Block    : {receipt.blockNumber}")
    log.info(f"  Gas used : {receipt.gasUsed}")
    log.info(f"  Status   : {'SUCCESS' if receipt.status == 1 else 'FAILED'}")

    # Store gas info in report metadata for Section 6.2 table
    report.metadata[f"gas_used_registration"] = receipt.gasUsed
    report.metadata[f"block_number"] = receipt.blockNumber

    # ── Measure provenance log write-back ─────────────────────────────────────
    with Timer() as t_db:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE governance.provenance_log
                SET blockchain_tx = :tx_hash
                WHERE id = :log_id
            """), {
                "tx_hash": tx_hash_hex,
                "log_id": provenance_log_id
            })

    report.add(
        operation="Provenance log write-back (PostGIS)",
        duration_s=t_db.elapsed,
        notes=f"Updated provenance_log id={provenance_log_id} with TX hash"
    )
    log.info(f"Provenance log updated in {t_db.elapsed:.4f}s")

    return tx_hash_hex


def validate_index_version(version_id: int, report: TimingReport) -> str:
    """Validate an index version on-chain. Measured separately."""
    log.info(f"Validating index version {version_id} on blockchain...")

    with Timer() as t:
        tx_hash = contract.functions.validateIndexVersion(
            version_id
        ).transact({
            "from": DEPLOYER_ADDRESS,
            "gas": 200000
        })
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    tx_hash_hex = receipt.transactionHash.hex()

    report.add(
        operation="validateIndexVersion TX",
        duration_s=t.elapsed,
        notes=f"Gas used: {receipt.gasUsed}"
    )
    report.metadata["gas_used_validation"] = receipt.gasUsed

    log.info(f"Validated in {t.elapsed:.4f}s · TX: {tx_hash_hex}")
    return tx_hash_hex


def verify_index_hash(version_id: int, data_hash: str) -> bool:
    """Verify hash against on-chain record. Read-only, no gas."""
    result = contract.functions.verifyIndexHash(
        version_id,
        data_hash
    ).call()
    return result


def get_index_version(version_id: int) -> dict:
    """Get on-chain details of an index version. Read-only, no gas."""
    result = contract.functions.getIndexVersion(version_id).call()
    return {
        "dataHash":  result[0],
        "layerName": result[1],
        "actor":     result[2],
        "timestamp": result[3],
        "validated": result[4]
    }


# ── MAIN — FULL INSTRUMENTED RUN ──────────────────────────────────────────────

if __name__ == "__main__":

    print("\n" + "=" * 52)
    print("  D3.4 LedgerInterface — Instrumented Run")
    print("=" * 52)
    print(f"  Blockchain connected : {w3.is_connected()}")
    print(f"  Contract address     : {CONTRACT_ADDRESS}")
    print(f"  Latest block         : {w3.eth.block_number}")
    print("=" * 52 + "\n")

    # Initialise the timing report for this run
    report = TimingReport()
    report.metadata["environment"] = "Hardhat local simulation"
    report.metadata["contract_address"] = CONTRACT_ADDRESS
    report.metadata["node_url"] = "http://127.0.0.1:8545"

    # ── Step 1: Fetch pending provenance record ───────────────────────────────
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, data_hash, layer_name, actor, metadata
            FROM governance.provenance_log
            WHERE blockchain_tx = 'PENDING_BLOCKCHAIN_REGISTRATION'
            ORDER BY id
            LIMIT 1
        """))
        record = result.fetchone()

    if not record:
        log.warning("No pending provenance records found. "
                    "Run the feature pipeline first to create a PENDING record.")
        exit(0)

    log_id     = record[0]
    data_hash  = record[1]
    layer_name = record[2]
    actor      = record[3]

    log.info(f"Found pending record: ID={log_id}, Layer={layer_name}")

    # ── Step 2: Compute hash from DB (Stage 3 of contribution workflow) ───────
    # This computes the hash fresh from the DB to measure hash computation time.
    # If your pipeline already computed and stored the hash, you can skip this
    # and just use data_hash from the provenance record directly.
    computed_hash = compute_hash_from_db(report)

    # Use the stored hash (already computed by pipeline) for registration
    # but record the fresh computation time above as the profiling evidence.

    # ── Step 3: Register on blockchain (Stage 4) ──────────────────────────────
    tx_hash = register_index_version(
        data_hash=data_hash,
        layer_name=layer_name,
        actor=actor,
        metadata_ref=f"PostGIS:governance.provenance_log:id={log_id}",
        provenance_log_id=log_id,
        report=report
    )

    # ── Step 4: Validate on blockchain ────────────────────────────────────────
    validate_index_version(version_id=1, report=report)

    # ── Step 5: Verify hash (read-only, not timed as it incurs no gas) ────────
    is_valid = verify_index_hash(version_id=1, data_hash=data_hash)
    log.info(f"Hash verification result: {is_valid}")
    report.metadata["hash_verified"] = is_valid

    # ── Step 6: Get on-chain record ───────────────────────────────────────────
    on_chain = get_index_version(version_id=1)
    log.info(f"On-chain record retrieved:")
    log.info(f"  Layer     : {on_chain['layerName']}")
    log.info(f"  Actor     : {on_chain['actor']}")
    log.info(f"  Validated : {on_chain['validated']}")

    report.metadata["on_chain_validated"] = on_chain["validated"]

    # ── Step 7: Print and save report ─────────────────────────────────────────
    report.print_summary()
    saved_path = report.save()
    print(f"\n  Report saved to: {saved_path}")
    print("\n=== Run complete ===\n")
