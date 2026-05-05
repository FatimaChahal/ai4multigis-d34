# AI4MultiGIS / D3.4: Blockchain & DLT-based Decentralised MultiGIS Data Management System

[![Project](https://img.shields.io/badge/Project-AI4MultiGIS-185FA5)](https://www.ai4multigis.eu)
[![Deliverable](https://img.shields.io/badge/Deliverable-D3.4-0F6E56)](https://github.com/FatimaChahal/ai4multigis-d34)
[![Release](https://img.shields.io/badge/Release-v1.0--month20-854F0B)](https://github.com/FatimaChahal/ai4multigis-d34/releases/tag/v1.0-month20)
[![License](https://img.shields.io/badge/License-MIT-534AB7)](LICENSE)

---

## Overview

This repository contains the prototype implementation of **Deliverable D3.4** of the [AI4MultiGIS](https://www.ai4multigis.eu) project, funded under the **CHIST-ERA Call 2023** programme.

D3.4 implements a **decentralised, blockchain-based governance layer** for geospatial analytical indices produced within the AI4MultiGIS MultiGIS framework. The system provides immutable provenance recording, cryptographic integrity verification, and role-based access control for geospatial data contributions across multiple institutional partners and application domains.

The prototype has been validated across two pilot case studies:
- **Pilot 1**  SuDS flood risk management (Chelmsford, UK) with 3,122 MASTER_GRID cells
- **Pilot 2**  Invasive freshwater species monitoring (World of Crayfish, Europe) with 1,065 occurrence records

---

## Architecture

\`\`\`
┌─────────────────────────────────────────────────────────────┐
│                   Python Pipeline Layer                      │
│   Feature Engineering  →  LedgerInterface  →  PostGIS        │
└────────────────────────────┬────────────────────────────────┘
                             │ SHA-256 hash + TX
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              Blockchain Governance Layer (Hardhat)           │
│   GISIndexRegistry  ·  AccessController  ·  ProvenanceLogger │
└─────────────────────────────────────────────────────────────┘
                             │ TX hash write-back
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostGIS / Docker                          │
│   raw_data  ·  processed_data  ·  governance.provenance_log  │
└─────────────────────────────────────────────────────────────┘
\`\`\`

The system operates across four sequential stages:
1. **Raw data ingestion** : vector and raster datasets into PostGIS \`raw_data\` schema
2. **Feature engineering** : spatial grid construction and feature vector computation
3. **Hash computation** : SHA-256 fingerprint of the complete analytical index snapshot
4. **On-chain registration** : hash and provenance metadata submitted to \`GISIndexRegistry\`

---

## Repository Structure

\`\`\`
ai4multigis-d34/
├── blockchain/
│   ├── contracts/
│   │   └── GISIndexRegistry.sol          # Core governance smart contract
│   ├── scripts/
│   │   └── deploy.js                     # Hardhat deployment script
│   ├── Ledger_interface_instrumented.py  # Instrumented Python middleware
│   └── hardhat.config.js
├── pipeline/
│   ├── ingest_woc_pilot2.py              # Pilot 2 WoC data ingestion
│   ├── scalability_test.py               # 20-version sequential load test
│   ├── fault_tolerance_test.py           # 7-scenario fault tolerance suite
│   └── generate_pilot2_figures.py        # Publication figures generator
├── config/
│   ├── schema.sql                        # PostGIS database schema
│   └── .env.template                     # Environment variable template
├── profiling/                            # Timing and test reports (JSON)
└── requirements.txt
\`\`\`

---

## Smart Contract

The core governance contract \`GISIndexRegistry.sol\` implements:

| Function | Role required | Description |
|---|---|---|
| \`registerIndexVersion()\` | DataProvider | Register a new index version with SHA-256 hash |
| \`validateIndexVersion()\` | Administrator | Validate a pending index version |
| \`rejectIndexVersion()\` | Administrator | Reject with recorded reason |
| \`verifyIndexHash()\` | Public (read-only) | Verify hash against on-chain record |
| \`getIndexVersion()\` | Public (read-only) | Retrieve full version metadata |

**Deployed address (local Hardhat):** \`0x5FbDB2315678afecb367f032d93F642f64180aa3\`

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Pipeline and LedgerInterface |
| Node.js | 22.x | Hardhat blockchain framework |
| Docker | Latest | PostGIS database container |
| Hardhat | 2.x | Local blockchain simulation |
| PostgreSQL/PostGIS | 15 / 3.3 | Geospatial data storage |

---

## Setup Instructions

### 1 — Clone the repository
\`\`\`bash
git clone https://github.com/FatimaChahal/ai4multigis-d34.git
cd ai4multigis-d34
\`\`\`

### 2 — Configure environment
\`\`\`bash
cp config/.env.template config/.env
# Edit config/.env with your database credentials
\`\`\`

### 3 — Start PostGIS
\`\`\`bash
docker run -d \
  --name ai4multigis_postgis \
  -e POSTGRES_DB=ai4multigis_db \
  -e POSTGRES_USER=ai4multigis \
  -e POSTGRES_PASSWORD=ai4multigis \
  -p 5433:5432 \
  postgis/postgis:15-3.3

# Apply schema
psql -h localhost -p 5433 -U ai4multigis -d ai4multigis_db -f config/schema.sql
\`\`\`

### 4 — Install Python dependencies
\`\`\`bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
\`\`\`

### 5 — Install Node.js dependencies and start Hardhat
\`\`\`bash
cd blockchain
npm install
npx hardhat node   # Keep this terminal open
\`\`\`

### 6 — Deploy the smart contract
\`\`\`bash
# In a new terminal
cd blockchain
npx hardhat run scripts/deploy.js --network localhost
\`\`\`

### 7 — Run the governance pipeline (Pilot 1)
\`\`\`bash
cd ..
python3 blockchain/Ledger_interface_instrumented.py
\`\`\`

### 8 — Run the Pilot 2 ingestion
\`\`\`bash
python3 pipeline/ingest_woc_pilot2.py
\`\`\`

---

## Evaluation Scripts

### Performance profiling
\`\`\`bash
python3 blockchain/Ledger_interface_instrumented.py
# Reports saved to: profiling/timing_report_*.json
\`\`\`

### Scalability test
\`\`\`bash
python3 pipeline/scalability_test.py
# Report saved to: profiling/scalability_report_*.json
\`\`\`

### Fault tolerance test
\`\`\`bash
python3 pipeline/fault_tolerance_test.py
# Report saved to: profiling/fault_tolerance_report_*.json
\`\`\`

### Generate Pilot 2 figures
\`\`\`bash
python3 pipeline/generate_pilot2_figures.py
# Output: outputs/figures/Pilot2_Fig{1,2,3}*.png
\`\`\`

---

## Key Results (Month 20)

| Metric | Result |
|---|---|
| Functional validation | 8/8 components validated |
| Governance cycle latency (Pilot 1) | 32.5 ms mean (3 runs) |
| Governance cycle latency (Pilot 2) | 25.0 ms mean (3 runs) |
| Gas cost per registration (stable) | 243,086 gas (versions 2–20) |
| Scalability test | 20/20 versions · 100% success rate |
| Fault tolerance test | 7/7 scenarios passed |
| Pilot-agnostic operation | Confirmed across 2 domains |

---

## Pilot Case Studies

### Pilot 1 — SuDS Flood Risk Management (Chelmsford, UK)
- **Partner:** ARU / UPPA
- **Dataset:** 7,679,438 vector features · 166 raster files
- **MASTER_GRID:** 3,122 cells · 500m resolution · 6 flood risk indicators
- **Governance:** SHA-256 hash registered on-chain · provenance log in PostGIS

### Pilot 2 — Invasive Freshwater Species (World of Crayfish)
- **Partner:** UPPA
- **Dataset:** 1,065 occurrence records · 21 species · Europe 1994–2025
- **Status:** Data ingested and governed · Romanian MASTER_GRID planned
- **Governance:** Full provenance chain demonstrated · TX hash on-chain

---

## Related Deliverables

| Deliverable | Title | Relation |
|---|---|---|
| D2.3 | Responsible AI Framework | RAI principles implemented in D3.4 |
| D3.1 | MultiGIS Data Model | Data schema foundation |
| D3.2 | Synthetic Data Generation | Pilot 1 test data source |
| D5.2 | Responsible AI Policy | Full RAI policy built on D3.4 evidence |

---

## Citation

\`\`\`
Chahal, F. et al. (2026). D3.4: Blockchain & DLT-based Decentralised
MultiGIS Data Management System. AI4MultiGIS Project (CHIST-ERA Call 2023).
University of Pau and the Adour Region (UPPA).
https://github.com/FatimaChahal/ai4multigis-d34
\`\`\`

---

## Team

- **Fatima Chahal** — UPPA/LIUPPA (Task T3.4 lead)
- **AI4MultiGIS Consortium** — ARU · UPPA · UVT · LUT

---

## Funding

This work is supported by the **CHIST-ERA Call 2023** programme under the AI4MultiGIS project.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
