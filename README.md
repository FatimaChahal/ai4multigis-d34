# AI4MultiGIS — D3.4 Blockchain & DLT Data Management System

**EU Project:** AI4MultiGIS | **Work Package:** WP3 — Task T3.4  
**Institution:** UPPA (Université de Pau et des Pays de l'Adour)  
**Author:** Fatima Chahal

---

## Overview

This repository implements the D3.4 deliverable: a decentralised data management system combining geospatial processing (PostGIS) with blockchain-based provenance governance (Hyperledger Besu QBFT).

Two pilots are covered:
- **Pilot 1 — Chelmsford SuDS** (UK): flood risk spatial analytics over a 500m MASTER_GRID index
- **Pilot 2 — World of Crayfish (WoC)**: invasive freshwater species occurrence governance across Europe

---

## Architecture
PostGIS (Docker)          Hyperledger Besu QBFT (Docker)
│                              │
│  SHA-256 hash                │
└──────────────────────────────┤
│
┌─────────┴──────────┐
│  Smart Contracts    │
│  GISIndexRegistry   │
│  AccessController   │
│  ProvenanceLogger   │
└────────────────────┘

---

## Project Structure
D3.4/
├── blockchain/                  # Smart contracts & deployment
│   ├── contracts/               # Solidity contracts
│   │   ├── GISIndexRegistry.sol
│   │   ├── AccessController.sol
│   │   └── ProvenanceLogger.sol
│   ├── scripts/
│   │   ├── deploy.js            # Deploy GISIndexRegistry
│   │   └── deploy_all.js        # Deploy all 3 contracts
│   ├── ledger_interface.py      # Python blockchain API
│   ├── Ledger_interface_instrumented.py  # Instrumented for Section 6.2
│   └── hardhat.config.js
├── pipeline/                    # GIS processing pipeline
│   ├── build_master_grid.py     # Pilot 1: MASTER_GRID construction
│   ├── ingest_woc_pilot2.py     # Pilot 2: WoC ingestion + governance
│   ├── scalability_test.py
│   └── fault_tolerance_test.py
├── ingestion/                   # Data ingestion modules
├── config/
│   ├── .env.template            # Environment template (copy to .env)
│   ├── contract_config.json     # Deployed contract addresses
│   └── schema.sql               # PostgreSQL schema
├── besu-network/
│   └── config/genesis.json      # Besu QBFT genesis block
├── profiling/                   # Performance timing reports (JSON)
├── main_with_blockchain.py      # Full end-to-end pipeline orchestrator
└── main.py                      # Original pipeline entry point

---

## Prerequisites

- Docker Desktop (WSL2 integration enabled)
- Python 3.12+ with virtualenv
- Node.js 18+

---

## Setup

### 1. Clone and configure environment

```bash
git clone <repo-url>
cd D3.4
python3 -m venv .venv && source .venv/bin/activate
pip install web3 geopandas sqlalchemy psycopg2-binary python-dotenv eth-account
cp config/.env.template config/.env
# Edit config/.env with your credentials
```

### 2. Start infrastructure

```bash
# PostGIS
docker run -d --name postgis-db -p 5433:5432 \
  -e POSTGRES_USER=ai4multigis \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=ai4multigis_db \
  postgis/postgis:16-3.4

# Hyperledger Besu QBFT
docker run -d --name besu-node1 -p 8545:8545 \
  -v ./besu-network/config:/config \
  -v ./besu-network/data/node1:/data \
  hyperledger/besu:latest \
  --data-path=/data --genesis-file=/config/genesis.json \
  --rpc-http-enabled --rpc-http-host=0.0.0.0 --rpc-http-port=8545 \
  --rpc-http-api=ETH,NET,QBFT,MINER,WEB3,ADMIN \
  --host-allowlist="*" --min-gas-price=0 --tx-pool-min-gas-price=0
```

### 3. Deploy smart contracts

```bash
cd blockchain
npx hardhat compile
npx hardhat run scripts/deploy_all.js --network besu
```

### 4. Run the full pipeline

```bash
cd ..
python main_with_blockchain.py
```

---

## Smart Contracts

| Contract | Address (local) | Purpose |
|---|---|---|
| GISIndexRegistry | see contract_config.json | Versioned GIS index registration |
| AccessController | see contract_config.json | Role-based access control |
| ProvenanceLogger | see contract_config.json | Immutable audit trail |

---

## Performance (Section 6.2)

Measured on Hyperledger Besu QBFT, block period = 2s, 3 runs each:

| Operation | Pilot 1 Mean | Pilot 2 Mean |
|---|---|---|
| SHA-256 hash | 0.011s | 0.001s |
| TX submission | 0.029s | 0.022s |
| TX confirmation | 0.936s | 0.726s |
| Provenance write | 0.004s | 0.002s |
| **Total cycle** | **2.942s** | **1.265s** |

---

## Data

Source datasets are not included in this repository due to size and licensing:
- Pilot 1: OS OpenData (flood risk, road network, rivers) — available from [data.gov.uk](https://www.data.gov.uk)
- Pilot 2: World of Crayfish database v1.2 — available from [woc.iframe.eu](https://woc.iframe.eu)

---

## License

This project is part of the AI4MultiGIS EU research project. All rights reserved.
