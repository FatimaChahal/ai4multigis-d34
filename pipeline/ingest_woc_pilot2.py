"""
Pilot 2 — World of Crayfish (WoC) Data Ingestion Script
D3.4 AI4MultiGIS — Invasive Freshwater Species Pilot
"""
import hashlib, json, os, time, logging
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from web3 import Web3

load_dotenv("/home/fatima/D3.4/config/.env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("WoC-Ingestion")

EXCEL_PATH   = "/home/fatima/D3.4/data/database-WoC1_2.xlsx"
OUTPUT_DIR   = "/home/fatima/D3.4/profiling"
ACTOR        = "UPPA/Fatima_Chahal"
LAYER_NAME   = "WoC_CRAYFISH_OCCURRENCES"

engine = create_engine(f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
from web3.middleware import ExtraDataToPOAMiddleware
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
from eth_account import Account
_pk = os.getenv("BESU_PRIVATE_KEY")
if not _pk:
    raise EnvironmentError("BESU_PRIVATE_KEY not set in config/.env")
_account = Account.from_key(_pk)

with open("/home/fatima/D3.4/config/contract_config.json") as f:
    cfg = json.load(f)
with open("/home/fatima/D3.4/blockchain/artifacts/contracts/GISIndexRegistry.sol/GISIndexRegistry.json") as f:
    CONTRACT_ABI = json.load(f)["abi"]

contract = w3.eth.contract(address=cfg["contractAddress"], abi=CONTRACT_ABI)

class Timer:
    def __enter__(self): self._s = time.perf_counter(); return self
    def __exit__(self, *a): self.elapsed = time.perf_counter() - self._s

@dataclass
class Report:
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    records: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    def add(self, op, dur, notes=""): self.records.append({"operation": op, "duration_s": round(dur,4), "notes": notes})
    def total(self): return round(sum(r["duration_s"] for r in self.records), 4)
    def print_summary(self):
        print("\n" + "="*56)
        print("  D3.4 Performance Profile — Pilot 2 (WoC)")
        print("="*56)
        for r in self.records: print(f"  {r['operation']:<38}: {r['duration_s']:.4f} s")
        print("-"*56)
        print(f"  {'Total governance cycle':<38}: {self.total():.4f} s")
        print("="*56)
    def save(self):
        Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        p = Path(OUTPUT_DIR) / f"timing_report_pilot2_{self.run_id}.json"
        with open(p, "w") as f:
            json.dump({"run_id": self.run_id, "pilot": "Pilot 2", "total_s": self.total(), "records": self.records, "metadata": self.metadata}, f, indent=2)
        log.info(f"Report saved: {p}")
        return str(p)

# ── STEP 1: LOAD DATA ─────────────────────────────────────────────────────────
def load_data():
    log.info(f"Loading WoC dataset...")
    df = pd.read_excel(EXCEL_PATH)
    df.columns = ['woc_id','doi','url','citation','latitude','longitude','accuracy',
                  'species_name','status','year_of_record','ncbi_coi_1','ncbi_16s_1',
                  'ncbi_sra','claim_extinction','pathogen_name','ncbi_coi_2','ncbi_16s_2',
                  'genotype_group','haplotype','year_record_2','comments',
                  'confidentiality_level','contributor']
    df['latitude']  = pd.to_numeric(df['latitude'],  errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df['year_of_record'] = pd.to_numeric(df['year_of_record'], errors='coerce')
    df = df.dropna(subset=['latitude','longitude'])
    log.info(f"Loaded {len(df)} valid records | {df['species_name'].nunique()} species")
    return df

# ── STEP 2: INGEST TO POSTGIS ─────────────────────────────────────────────────
def ingest(df, report):
    log.info("Creating table and ingesting records...")
    with engine.begin() as conn:
        conn.execute(text("""
            DROP TABLE IF EXISTS raw_data.woc_occurrences CASCADE;
            CREATE TABLE raw_data.woc_occurrences (
                id SERIAL PRIMARY KEY,
                woc_id VARCHAR(20) UNIQUE,
                geom GEOMETRY(Point, 4326),
                species_name TEXT,
                status VARCHAR(50),
                year_of_record INTEGER,
                accuracy VARCHAR(20),
                contributor TEXT,
                comments TEXT,
                doi TEXT,
                confidentiality INTEGER,
                properties JSONB,
                ingested_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX idx_woc_geom ON raw_data.woc_occurrences USING GIST(geom);
        """))

    inserted = 0
    skipped  = 0
    with Timer() as t:
        with engine.begin() as conn:
            for _, row in df.iterrows():
                try:
                    props = json.dumps({"woc_id": row["woc_id"], "species_name": row["species_name"], "status": row["status"], "accuracy": row["accuracy"]})
                    conn.execute(text(
                        "INSERT INTO raw_data.woc_occurrences "
                        "(woc_id, geom, species_name, status, year_of_record, accuracy, contributor, comments, doi, confidentiality, properties) "
                        "VALUES (:woc_id, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :species, :status, :year, :accuracy, :contributor, :comments, :doi, :conf, cast(:props as jsonb)) "
                        "ON CONFLICT (woc_id) DO NOTHING"
                    ), {
                        "woc_id": row["woc_id"],
                        "lon": float(row["longitude"]),
                        "lat": float(row["latitude"]),
                        "species": row["species_name"],
                        "status": row["status"],
                        "year": int(row["year_of_record"]) if pd.notna(row["year_of_record"]) else None,
                        "accuracy": row["accuracy"],
                        "contributor": row["contributor"],
                        "comments": str(row["comments"]) if pd.notna(row["comments"]) else None,
                        "doi": str(row["doi"]) if pd.notna(row["doi"]) else None,
                        "conf": int(row["confidentiality_level"]) if pd.notna(row["confidentiality_level"]) else 0,
                        "props": props
                    })
                    inserted += 1
                except Exception as e:
                    skipped += 1

    report.add("WoC data ingestion to PostGIS", t.elapsed, f"{inserted} records inserted, {skipped} skipped")
    report.metadata["records_ingested"] = inserted
    log.info(f"Ingestion complete in {t.elapsed:.4f}s — {inserted} inserted, {skipped} skipped")
    return inserted

# ── STEP 3: HASH ──────────────────────────────────────────────────────────────
def compute_hash(report):
    log.info("Computing SHA-256 hash...")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT woc_id, ST_AsText(geom), species_name, status, year_of_record FROM raw_data.woc_occurrences ORDER BY woc_id")).fetchall()
    log.info(f"Fetched {len(rows)} records for hashing.")
    with Timer() as t:
        data_hash = hashlib.sha256(json.dumps([list(r) for r in rows], default=str).encode()).hexdigest()
    report.add("SHA-256 hash computation (WoC layer)", t.elapsed, f"{len(rows)} occurrence records")
    report.metadata["woc_record_count"] = len(rows)
    log.info(f"Hash computed in {t.elapsed:.4f}s : {data_hash[:32]}...")
    return data_hash

# ── STEP 4: ON-CHAIN REGISTRATION ─────────────────────────────────────────────
def register(data_hash, report):
    log.info("Registering on blockchain...")
    with Timer() as t_sub:
        fn = contract.functions.registerIndexVersion(data_hash, LAYER_NAME, ACTOR, f"PostGIS:raw_data.woc_occurrences")
        tx_built = fn.build_transaction({"from": _account.address, "gas": 500000, "gasPrice": 0, "nonce": w3.eth.get_transaction_count(_account.address), "chainId": 1337})
        signed = _account.sign_transaction(tx_built)
        tx = w3.eth.send_raw_transaction(signed.raw_transaction)
    report.add("TX submission to GISIndexRegistry", t_sub.elapsed, "WoC layer")
    with Timer() as t_con:
        receipt = w3.eth.wait_for_transaction_receipt(tx)
    tx_hex = receipt.transactionHash.hex()
    report.add("TX confirmation (block inclusion)", t_con.elapsed, f"Block #{receipt.blockNumber} · Gas: {receipt.gasUsed}")
    report.metadata.update({"gas_used": receipt.gasUsed, "tx_hash": tx_hex})
    log.info(f"TX submitted in {t_sub.elapsed:.4f}s, confirmed in {t_con.elapsed:.4f}s")
    log.info(f"  TX Hash: {tx_hex} | Block: {receipt.blockNumber} | Gas: {receipt.gasUsed} | Status: {'SUCCESS' if receipt.status==1 else 'FAILED'}")
    return tx_hex

# ── STEP 5: PROVENANCE ────────────────────────────────────────────────────────
def write_provenance(data_hash, tx_hash, report):
    log.info("Writing provenance record...")
    meta = json.dumps({"source": "World of Crayfish (WoC) database", "pilot": "Pilot 2", "records": report.metadata.get("woc_record_count", 0), "species": 21, "coverage": "Europe 1994-2025"})
    with Timer() as t:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO governance.provenance_log (event_type, layer_name, actor, data_hash, blockchain_tx, metadata) "
                "VALUES ('INDEX_CREATION', :layer, :actor, :data_hash, :tx_hash, cast(:meta as jsonb))"
            ), {"layer": LAYER_NAME, "actor": ACTOR, "data_hash": data_hash, "tx_hash": tx_hash, "meta": meta})
    report.add("Provenance log write-back (PostGIS)", t.elapsed, "WoC governance record")
    log.info(f"Provenance written in {t.elapsed:.4f}s")

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*56)
    print("  D3.4 Pilot 2 — WoC Data Ingestion & Governance")
    print("="*56)
    print(f"  Blockchain connected : {w3.is_connected()}")
    print(f"  Contract address     : {cfg['contractAddress']}")
    print(f"  Latest block         : {w3.eth.block_number}")
    print("="*56 + "\n")

    report = Report()
    report.metadata["environment"] = "Hardhat local simulation"
    report.metadata["dataset"] = "World of Crayfish (WoC) v1.2"

    df        = load_data()
    ingest(df, report)
    data_hash = compute_hash(report)
    tx_hash   = register(data_hash, report)
    write_provenance(data_hash, tx_hash, report)

    report.print_summary()
    saved = report.save()
    print(f"\n  Report saved to: {saved}")
    print("\n=== Pilot 2 ingestion complete ===\n")
