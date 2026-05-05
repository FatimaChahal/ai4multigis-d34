from web3 import Web3
import json

# Connect to Hardhat
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

# Load contract config
with open("/home/fatima/D3.4/config/contract_config.json") as f:
    cfg = json.load(f)

# Load ABI
with open("/home/fatima/D3.4/blockchain/artifacts/contracts/GISIndexRegistry.sol/GISIndexRegistry.json") as f:
    abi = json.load(f)["abi"]

# Connect to contract
contract = w3.eth.contract(
    address=cfg["contractAddress"],
    abi=abi
)

# Administrator account (account 0 — the deployer)
admin = w3.eth.accounts[0]

# Version to validate — Pilot 2 version ID
# Check which version ID was assigned during your 3 runs
version_id = 1  # adjust if needed

# Call validateIndexVersion
import time
t_start = time.perf_counter()
tx_hash = contract.functions.validateIndexVersion(version_id).transact({
    "from": admin
})
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
t_end = time.perf_counter()

gas_used = receipt.gasUsed
elapsed  = t_end - t_start

print(f"TX Hash  : {tx_hash.hex()}")
print(f"Block    : {receipt.blockNumber}")
print(f"Gas used : {gas_used}")
print(f"Status   : {'SUCCESS' if receipt.status == 1 else 'FAILED'}")
print(f"Time     : {elapsed:.4f}s")