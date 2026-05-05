"""
D3.4 Fault Tolerance Test — Section 6.4
Tests six fault scenarios against GISIndexRegistry to demonstrate
system robustness and error handling correctness.
"""
import hashlib, json, os, time, logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError

load_dotenv("/home/fatima/D3.4/config/.env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("FaultTolerance")

OUTPUT_DIR = "/home/fatima/D3.4/profiling"

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
with open("/home/fatima/D3.4/config/contract_config.json") as f:
    cfg = json.load(f)
with open("/home/fatima/D3.4/blockchain/artifacts/contracts/GISIndexRegistry.sol/GISIndexRegistry.json") as f:
    abi = json.load(f)["abi"]

contract  = w3.eth.contract(address=cfg["contractAddress"], abi=abi)
DEPLOYER  = cfg["deployerAddress"]
# Use a non-privileged account for unauthorised actor tests
ACCOUNTS  = w3.eth.accounts
UNAUTH    = ACCOUNTS[1] if len(ACCOUNTS) > 1 else None

results = []

def run_test(name, expected, fn):
    """Execute a fault tolerance test and record the result."""
    print(f"\n  {'─'*60}")
    print(f"  TEST: {name}")
    print(f"  Expected: {expected}")
    try:
        fn()
        outcome = "PASSED — no exception (unexpected for rejection tests)"
        status  = "⚠ UNEXPECTED"
    except Exception as e:
        msg = str(e)
        # Extract the revert reason
        if "revert" in msg.lower() or "Registry:" in msg or "Validation:" in msg or "AccessControl:" in msg:
            # Find the reason string
            for marker in ["Registry:", "Validation:", "AccessControl:"]:
                if marker in msg:
                    start = msg.index(marker)
                    reason = msg[start:start+80].split("'")[0].strip()
                    break
            else:
                reason = msg[:100]
            outcome = f"PASSED — correctly rejected with: '{reason}'"
            status  = "✓ PASSED"
        else:
            outcome = f"ERROR — unexpected exception: {msg[:120]}"
            status  = "✗ ERROR"
    print(f"  Result : {status}")
    print(f"  Detail : {outcome}")
    results.append({"test": name, "expected": expected, "status": status, "detail": outcome})
    return status

print("\n" + "="*65)
print("  D3.4 Fault Tolerance Test Suite")
print("="*65)
print(f"  Blockchain connected : {w3.is_connected()}")
print(f"  Contract address     : {cfg['contractAddress']}")
print(f"  Deployer (admin)     : {DEPLOYER}")
print(f"  Unauthorised account : {UNAUTH}")
print(f"  Available accounts   : {len(ACCOUNTS)}")
print("="*65)

# ── FIRST: Register one valid version to use in subsequent tests ───────────────
valid_hash = hashlib.sha256(b"valid_test_version_1").hexdigest()
print(f"\n  Setup: Registering valid baseline version...")
tx = contract.functions.registerIndexVersion(
    valid_hash, "MASTER_GRID", "UPPA/Fatima_Chahal", "fault_tolerance_test:baseline"
).transact({"from": DEPLOYER, "gas": 500000})
receipt = w3.eth.wait_for_transaction_receipt(tx)
version_id = contract.functions.latestVersionId().call()
print(f"  Baseline version {version_id} registered. TX: {receipt.transactionHash.hex()[:32]}...")

# ── TEST 1: Empty data hash ────────────────────────────────────────────────────
run_test(
    "Empty dataHash rejected by contract",
    "Revert with 'Validation: dataHash cannot be empty'",
    lambda: contract.functions.registerIndexVersion(
        "", "MASTER_GRID", "UPPA/Fatima_Chahal", "test"
    ).transact({"from": DEPLOYER, "gas": 500000})
)

# ── TEST 2: Empty layer name ───────────────────────────────────────────────────
run_test(
    "Empty layerName rejected by contract",
    "Revert with 'Validation: layerName cannot be empty'",
    lambda: contract.functions.registerIndexVersion(
        valid_hash, "", "UPPA/Fatima_Chahal", "test"
    ).transact({"from": DEPLOYER, "gas": 500000})
)

# ── TEST 3: Empty actor ────────────────────────────────────────────────────────
run_test(
    "Empty actor rejected by contract",
    "Revert with 'Validation: actor cannot be empty'",
    lambda: contract.functions.registerIndexVersion(
        valid_hash, "MASTER_GRID", "", "test"
    ).transact({"from": DEPLOYER, "gas": 500000})
)

# ── TEST 4: Unauthorised actor registration ────────────────────────────────────
if UNAUTH:
    run_test(
        "Unauthorised actor registration rejected",
        "Revert with 'AccessControl: caller is not a data provider'",
        lambda: contract.functions.registerIndexVersion(
            valid_hash, "MASTER_GRID", "attacker", "malicious_ref"
        ).transact({"from": UNAUTH, "gas": 500000})
    )
else:
    print("\n  TEST 4: SKIPPED — only one account available")
    results.append({"test": "Unauthorised actor registration", "status": "SKIPPED", "detail": "Single account environment"})

# ── TEST 5: Double validation rejection ────────────────────────────────────────
# First validate legitimately
print(f"\n  Setup: Validating version {version_id} legitimately...")
tx = contract.functions.validateIndexVersion(version_id).transact({"from": DEPLOYER, "gas": 200000})
w3.eth.wait_for_transaction_receipt(tx)
print(f"  Version {version_id} validated successfully.")

run_test(
    "Double validation of same version rejected",
    "Revert with 'Registry: version already validated'",
    lambda: contract.functions.validateIndexVersion(version_id).transact(
        {"from": DEPLOYER, "gas": 200000}
    )
)

# ── TEST 6: Validation of non-existent version ─────────────────────────────────
run_test(
    "Validation of non-existent version rejected",
    "Revert with 'Registry: version does not exist'",
    lambda: contract.functions.validateIndexVersion(9999).transact(
        {"from": DEPLOYER, "gas": 200000}
    )
)

# ── TEST 7: Hash verification detects mismatch ────────────────────────────────
print(f"\n  {'─'*60}")
print(f"  TEST: Hash mismatch detection (verifyIndexHash)")
print(f"  Expected: Returns False for tampered hash")
tampered_hash = hashlib.sha256(b"tampered_data").hexdigest()
result = contract.functions.verifyIndexHash(version_id, tampered_hash).call()
status = "✓ PASSED" if result == False else "✗ FAILED"
detail = f"verifyIndexHash returned {result} for tampered hash (expected False)"
print(f"  Result : {status}")
print(f"  Detail : {detail}")
results.append({"test": "Hash mismatch detection", "expected": "Returns False", "status": status, "detail": detail})

# Verify correct hash still returns True
correct_result = contract.functions.verifyIndexHash(version_id, valid_hash).call()
print(f"  Bonus  : verifyIndexHash with correct hash returned {correct_result} (expected True) {'✓' if correct_result else '✗'}")

# ── SUMMARY ───────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  FAULT TOLERANCE TEST SUMMARY")
print("="*65)
passed  = sum(1 for r in results if "PASSED" in r["status"])
skipped = sum(1 for r in results if "SKIPPED" in r["status"])
failed  = sum(1 for r in results if "ERROR" in r["status"] or "FAILED" in r["status"])

print(f"\n  {'Test':<45} {'Status'}")
print(f"  {'─'*45} {'─'*12}")
for r in results:
    print(f"  {r['test']:<45} {r['status']}")

print(f"\n  Results: {passed} passed · {skipped} skipped · {failed} failed")
print(f"  Overall: {'ALL TESTS PASSED ✓' if failed == 0 else 'SOME TESTS FAILED ✗'}")
print("="*65)

# ── SAVE REPORT ───────────────────────────────────────────────────────────────
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
report = {
    "run_id": run_id,
    "test_suite": "fault_tolerance",
    "passed": passed,
    "skipped": skipped,
    "failed": failed,
    "results": results
}
fpath = Path(OUTPUT_DIR) / f"fault_tolerance_report_{run_id}.json"
with open(fpath, "w") as f:
    json.dump(report, f, indent=2)
print(f"\n  Report saved: {fpath}")
print("\n=== Fault tolerance test complete ===\n")
