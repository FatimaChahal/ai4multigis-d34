from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
import json, os, hashlib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("/home/fatima/D3.4/config/.env")

# ── Blockchain connection ─────────────────────────────────────────────────────
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

PRIVATE_KEY = os.getenv("BESU_PRIVATE_KEY")
if not PRIVATE_KEY:
    raise EnvironmentError("BESU_PRIVATE_KEY not set in config/.env")
account  = Account.from_key(PRIVATE_KEY)
DEPLOYER = account.address

# ── Contract setup ────────────────────────────────────────────────────────────
config_path = Path("/home/fatima/D3.4/config/contract_config.json")
with open(config_path) as f:
    cfg = json.load(f)

def _load_contract(sol_name, address):
    abi_path = Path(
        f"/home/fatima/D3.4/blockchain/artifacts/contracts/"
        f"{sol_name}.sol/{sol_name}.json"
    )
    abi = json.load(open(abi_path))["abi"]
    return w3.eth.contract(address=address, abi=abi)

registry    = _load_contract("GISIndexRegistry",  cfg["contractAddress"])
access_ctrl = _load_contract("AccessController",  cfg["accessControllerAddress"])
prov_logger = _load_contract("ProvenanceLogger",  cfg["provenanceLoggerAddress"])


# ── Internal helper ───────────────────────────────────────────────────────────
def _send_tx(fn, gas=500000):
    """Sign and send a transaction locally, wait for receipt."""
    tx = fn.build_transaction({
        "from":     DEPLOYER,
        "gas":      gas,
        "gasPrice": 0,
        "nonce":    w3.eth.get_transaction_count(DEPLOYER),
        "chainId":  1337,
    })
    signed  = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash)


# ── GISIndexRegistry API ──────────────────────────────────────────────────────
def register_index_version(
    data_hash: str,
    layer_name: str,
    actor: str,
    metadata_ref: str,
) -> dict:
    """Register a GIS index version on-chain. Returns tx details."""
    if not w3.is_connected():
        raise ConnectionError("Cannot connect to Besu node at http://127.0.0.1:8545")
    receipt = _send_tx(registry.functions.registerIndexVersion(
        data_hash, layer_name, actor, metadata_ref
    ))
    version_id = registry.functions.latestVersionId().call()
    return {
        "tx_hash":      receipt.transactionHash.hex(),
        "block_number": receipt.blockNumber,
        "gas_used":     receipt.gasUsed,
        "status":       "SUCCESS" if receipt.status == 1 else "FAILED",
        "version_id":   version_id,
    }


def validate_index_version(version_id: int) -> dict:
    """Validate an index version on-chain (admin only)."""
    receipt = _send_tx(
        registry.functions.validateIndexVersion(version_id), gas=200000
    )
    return {
        "tx_hash": receipt.transactionHash.hex(),
        "status":  "SUCCESS" if receipt.status == 1 else "FAILED",
    }


def verify_index_hash(version_id: int, data_hash: str) -> bool:
    """Verify a hash against the on-chain validated record. Read-only."""
    return registry.functions.verifyIndexHash(version_id, data_hash).call()


def get_index_version(version_id: int) -> dict:
    """Read an index version record from the chain. Read-only."""
    r = registry.functions.getIndexVersion(version_id).call()
    return {
        "dataHash":  r[0],
        "layerName": r[1],
        "actor":     r[2],
        "timestamp": r[3],
        "validated": r[4],
    }


# ── AccessController API ──────────────────────────────────────────────────────
def grant_role(address: str, role: int) -> dict:
    """
    Grant a role to an address.
    Roles: 1=ANALYST, 2=DATA_PROVIDER, 3=ADMINISTRATOR
    """
    receipt = _send_tx(
        access_ctrl.functions.grantRole(address, role), gas=100000
    )
    return {
        "tx_hash": receipt.transactionHash.hex(),
        "status":  "SUCCESS" if receipt.status == 1 else "FAILED",
    }


def get_role(address: str) -> str:
    """Get the role of an address. Read-only."""
    role_map = {0: "NONE", 1: "ANALYST", 2: "DATA_PROVIDER", 3: "ADMINISTRATOR"}
    role_int = access_ctrl.functions.getRole(address).call()
    return role_map.get(role_int, "UNKNOWN")


def is_data_provider(address: str) -> bool:
    """Check if an address has DATA_PROVIDER or higher role. Read-only."""
    return access_ctrl.functions.isDataProvider(address).call()


# ── ProvenanceLogger API ──────────────────────────────────────────────────────
def log_operation(
    operation: str,
    input_hash: str,
    output_hash: str,
    actor: str,
    metadata_ref: str,
) -> dict:
    """
    Log a pipeline operation on-chain for immutable audit trail.
    Operations: INGEST, TRANSFORM, VALIDATE, REGISTER
    """
    receipt = _send_tx(prov_logger.functions.logOperation(
        operation, input_hash, output_hash, actor, metadata_ref
    ))
    entry_id = prov_logger.functions.entryCount().call()
    return {
        "tx_hash":  receipt.transactionHash.hex(),
        "block_number": receipt.blockNumber,
        "gas_used": receipt.gasUsed,
        "status":   "SUCCESS" if receipt.status == 1 else "FAILED",
        "entry_id": entry_id,
    }


def get_provenance_entry(entry_id: int) -> dict:
    """Read a provenance entry from the chain. Read-only."""
    r = prov_logger.functions.getEntry(entry_id).call()
    return {
        "operation":  r[0],
        "inputHash":  r[1],
        "outputHash": r[2],
        "actor":      r[3],
        "timestamp":  r[4],
    }


def verify_provenance_hash(entry_id: int, output_hash: str) -> bool:
    """Verify an output hash against a provenance entry. Read-only."""
    return prov_logger.functions.verifyOutputHash(entry_id, output_hash).call()


# ── Utility ───────────────────────────────────────────────────────────────────
def compute_gis_hash(data: dict) -> str:
    """Compute a deterministic SHA-256 hash of a GIS dataset descriptor."""
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


# ── Connectivity check ────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== LedgerInterface — Besu QBFT ===")
    print(f"Connected           : {w3.is_connected()}")
    print(f"Latest block        : {w3.eth.block_number}")
    print(f"GISIndexRegistry    : {cfg['contractAddress']}")
    print(f"AccessController    : {cfg['accessControllerAddress']}")
    print(f"ProvenanceLogger    : {cfg['provenanceLoggerAddress']}")
    print(f"Deployer role       : {get_role(DEPLOYER)}")
    print(f"Latest GIS version  : {registry.functions.latestVersionId().call()}")
    print(f"Provenance entries  : {prov_logger.functions.entryCount().call()}")
    print("=== OK ===")
