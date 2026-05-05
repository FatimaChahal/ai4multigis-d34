"""
D3.4 Scalability Test — Priority 4
Registers 20 consecutive index versions on GISIndexRegistry
and measures gas cost and confirmation time for each.
Proves version chain grows at stable, predictable cost.
"""
import hashlib, json, os, time, logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

load_dotenv("/home/fatima/D3.4/config/.env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("Scalability")

OUTPUT_DIR = "/home/fatima/D3.4/profiling"
N_VERSIONS = 20

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
with open("/home/fatima/D3.4/config/contract_config.json") as f:
    cfg = json.load(f)
with open("/home/fatima/D3.4/blockchain/artifacts/contracts/GISIndexRegistry.sol/GISIndexRegistry.json") as f:
    abi = json.load(f)["abi"]

contract = w3.eth.contract(address=cfg["contractAddress"], abi=abi)
DEPLOYER  = cfg["deployerAddress"]

class Timer:
    def __enter__(self): self._s = time.perf_counter(); return self
    def __exit__(self, *a): self.elapsed = time.perf_counter() - self._s

print("\n" + "="*65)
print("  D3.4 Scalability Test — 20 Sequential Version Registrations")
print("="*65)
print(f"  Blockchain connected : {w3.is_connected()}")
print(f"  Contract address     : {cfg['contractAddress']}")
print(f"  Starting block       : {w3.eth.block_number}")
print("="*65)
print(f"\n  {'Version':<10} {'Hash (preview)':<20} {'Submit (s)':<12} {'Confirm (s)':<13} {'Gas used':<12} {'Block'}")
print(f"  {'-'*10} {'-'*20} {'-'*12} {'-'*13} {'-'*12} {'-'*6}")

results = []

for i in range(1, N_VERSIONS + 1):
    # Generate a unique hash for each version
    test_hash = hashlib.sha256(
        f"scalability_test_version_{i}_timestamp_{time.time()}".encode()
    ).hexdigest()

    # Submit TX
    with Timer() as t_sub:
        tx = contract.functions.registerIndexVersion(
            test_hash,
            "MASTER_GRID",
            "UPPA/Fatima_Chahal",
            f"scalability_test:version_{i}"
        ).transact({"from": DEPLOYER, "gas": 500000})

    # Confirm TX
    with Timer() as t_con:
        receipt = w3.eth.wait_for_transaction_receipt(tx)

    result = {
        "version":     i,
        "hash_preview": test_hash[:16],
        "submit_s":    round(t_sub.elapsed, 4),
        "confirm_s":   round(t_con.elapsed, 4),
        "total_s":     round(t_sub.elapsed + t_con.elapsed, 4),
        "gas_used":    receipt.gasUsed,
        "block":       receipt.blockNumber,
        "tx_hash":     receipt.transactionHash.hex(),
        "status":      "SUCCESS" if receipt.status == 1 else "FAILED"
    }
    results.append(result)

    print(f"  {i:<10} {test_hash[:16]:<20} {t_sub.elapsed:<12.4f} {t_con.elapsed:<13.4f} {receipt.gasUsed:<12,} {receipt.blockNumber}")

# ── SUMMARY STATISTICS ────────────────────────────────────────────────────────
submit_times  = [r["submit_s"]  for r in results]
confirm_times = [r["confirm_s"] for r in results]
total_times   = [r["total_s"]   for r in results]
gas_values    = [r["gas_used"]  for r in results]

def mean(v): return round(sum(v)/len(v), 4)
def mn(v):   return min(v)
def mx(v):   return max(v)

print("\n" + "="*65)
print("  SUMMARY STATISTICS")
print("="*65)
print(f"  {'Metric':<35} {'Mean':>8} {'Min':>8} {'Max':>8}")
print(f"  {'-'*35} {'-'*8} {'-'*8} {'-'*8}")
print(f"  {'TX submission time (s)':<35} {mean(submit_times):>8.4f} {mn(submit_times):>8.4f} {mx(submit_times):>8.4f}")
print(f"  {'TX confirmation time (s)':<35} {mean(confirm_times):>8.4f} {mn(confirm_times):>8.4f} {mx(confirm_times):>8.4f}")
print(f"  {'Total per-version time (s)':<35} {mean(total_times):>8.4f} {mn(total_times):>8.4f} {mx(total_times):>8.4f}")
print(f"  {'Gas used per version':<35} {mean(gas_values):>8,.0f} {mn(gas_values):>8,} {mx(gas_values):>8,}")
print(f"  {'Success rate':<35} {sum(1 for r in results if r['status']=='SUCCESS')}/{N_VERSIONS:>14}")
print("="*65)

# First vs stable gas cost
print(f"\n  Gas cost pattern:")
print(f"    Version 1  (first write)  : {results[0]['gas_used']:,} gas")
print(f"    Version 2  (stable)       : {results[1]['gas_used']:,} gas")
print(f"    Version 10 (mid-chain)    : {results[9]['gas_used']:,} gas")
print(f"    Version 20 (end of test)  : {results[19]['gas_used']:,} gas")
print(f"    Stable cost (versions 2-20): {mean(gas_values[1:]):,.0f} gas mean")

# ── SAVE REPORT ───────────────────────────────────────────────────────────────
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
report = {
    "run_id": run_id,
    "test": "scalability_20_versions",
    "n_versions": N_VERSIONS,
    "summary": {
        "submit_mean_s":   mean(submit_times),
        "submit_min_s":    mn(submit_times),
        "submit_max_s":    mx(submit_times),
        "confirm_mean_s":  mean(confirm_times),
        "confirm_min_s":   mn(confirm_times),
        "confirm_max_s":   mx(confirm_times),
        "total_mean_s":    mean(total_times),
        "gas_version1":    results[0]["gas_used"],
        "gas_stable_mean": round(mean(gas_values[1:]), 1),
        "gas_min":         mn(gas_values),
        "gas_max":         mx(gas_values),
        "success_rate":    f"{sum(1 for r in results if r['status']=='SUCCESS')}/{N_VERSIONS}"
    },
    "versions": results
}

fpath = Path(OUTPUT_DIR) / f"scalability_report_{run_id}.json"
with open(fpath, "w") as f:
    json.dump(report, f, indent=2)

print(f"\n  Report saved: {fpath}")
print("\n=== Scalability test complete ===\n")
