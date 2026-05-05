import json
import os
from pathlib import Path
from web3 import Web3
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv("/home/fatima/D3.4/config/.env")

# Database connection
engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

# Blockchain connection
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

# Load contract config
config_path = Path("/home/fatima/D3.4/config/contract_config.json")
with open(config_path) as f:
    contract_config = json.load(f)

CONTRACT_ADDRESS = contract_config["contractAddress"]
DEPLOYER_ADDRESS = contract_config["deployerAddress"]

# Load contract ABI from compiled artifacts
abi_path = Path("/home/fatima/D3.4/blockchain/artifacts/contracts/GISIndexRegistry.sol/GISIndexRegistry.json")
with open(abi_path) as f:
    artifact = json.load(f)
    CONTRACT_ABI = artifact["abi"]

# Instantiate contract
contract = w3.eth.contract(
    address=CONTRACT_ADDRESS,
    abi=CONTRACT_ABI
)


def register_index_version(
    data_hash: str,
    layer_name: str,
    actor: str,
    metadata_ref: str,
    provenance_log_id: int
) -> str:
    """
    Register an index version on the blockchain and update
    the provenance log with the real transaction hash.
    """
    print(f"Registering index version on blockchain...")
    print(f"  Layer    : {layer_name}")
    print(f"  Actor    : {actor}")
    print(f"  Hash     : {data_hash[:32]}...")

    # Check connection
    if not w3.is_connected():
        raise ConnectionError("Cannot connect to blockchain node")

    # Build and send transaction
    tx_hash = contract.functions.registerIndexVersion(
        data_hash,
        layer_name,
        actor,
        metadata_ref
    ).transact({
        "from": DEPLOYER_ADDRESS,
        "gas": 500000
    })

    # Wait for confirmation
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    tx_hash_hex = receipt.transactionHash.hex()

    print(f"  TX Hash  : {tx_hash_hex}")
    print(f"  Block    : {receipt.blockNumber}")
    print(f"  Gas used : {receipt.gasUsed}")
    print(f"  Status   : {'SUCCESS' if receipt.status == 1 else 'FAILED'}")

    # Update provenance log with real transaction hash
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE governance.provenance_log
            SET blockchain_tx = :tx_hash
            WHERE id = :log_id
        """), {
            "tx_hash": tx_hash_hex,
            "log_id": provenance_log_id
        })

    print(f"  Provenance log updated with real TX hash")
    return tx_hash_hex


def validate_index_version(version_id: int) -> str:
    """Validate an index version on-chain."""
    print(f"Validating index version {version_id} on blockchain...")

    tx_hash = contract.functions.validateIndexVersion(
        version_id
    ).transact({
        "from": DEPLOYER_ADDRESS,
        "gas": 200000
    })

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    tx_hash_hex = receipt.transactionHash.hex()
    print(f"  Validated. TX Hash: {tx_hash_hex}")
    return tx_hash_hex


def verify_index_hash(version_id: int, data_hash: str) -> bool:
    """Verify a hash against the on-chain record."""
    result = contract.functions.verifyIndexHash(
        version_id,
        data_hash
    ).call()
    return result


def get_index_version(version_id: int) -> dict:
    """Get on-chain details of an index version."""
    result = contract.functions.getIndexVersion(version_id).call()
    return {
        "dataHash": result[0],
        "layerName": result[1],
        "actor": result[2],
        "timestamp": result[3],
        "validated": result[4]
    }


if __name__ == "__main__":
    print("=== LedgerInterface Test ===")
    print(f"Blockchain connected : {w3.is_connected()}")
    print(f"Contract address     : {CONTRACT_ADDRESS}")
    print(f"Latest block         : {w3.eth.block_number}")

    # Fetch the pending provenance record from the database
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
        print("No pending provenance records found.")
    else:
        log_id = record[0]
        data_hash = record[1]
        layer_name = record[2]
        actor = record[3]
        metadata = record[4]

        print(f"\nFound pending record: ID={log_id}, Layer={layer_name}")

        # Step 1: Register on blockchain
        tx_hash = register_index_version(
            data_hash=data_hash,
            layer_name=layer_name,
            actor=actor,
            metadata_ref=f"PostGIS:governance.provenance_log:id={log_id}",
            provenance_log_id=log_id
        )

        # Step 2: Validate on blockchain
        validate_index_version(version_id=1)

        # Step 3: Verify the hash
        is_valid = verify_index_hash(version_id=1, data_hash=data_hash)
        print(f"\nHash verification result: {is_valid}")

        # Step 4: Get on-chain record
        on_chain = get_index_version(version_id=1)
        print(f"\nOn-chain record:")
        print(f"  Layer     : {on_chain['layerName']}")
        print(f"  Actor     : {on_chain['actor']}")
        print(f"  Validated : {on_chain['validated']}")
        print(f"  Timestamp : {on_chain['timestamp']}")

    print("\n=== LedgerInterface Test Complete ===")
