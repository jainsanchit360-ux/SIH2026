# ResQtech (SIH26001)

> **AI-Based Early Warning and Landslide Risk Monitoring System in the North-Eastern Region (NER) of India**

[![Python 3.14](https://img.shields.io/badge/Python-3.14-blue.svg)](https://python.org)
[![FastAPI 0.1.0-prototype](https://img.shields.io/badge/FastAPI-0.1.0--prototype-green.svg)](https://fastapi.tiangolo.com)
[![React 19 + Vite 8](https://img.shields.io/badge/React-19-cyan.svg)](https://react.dev)
[![License: Prototype](https://img.shields.io/badge/License-SIH--2026-orange.svg)]()

---

## System Overview

ResQtech is a multi-tier AI and GIS risk decision support platform engineered for landslide monitoring in India's North-Eastern Region (NER). Built for Smart India Hackathon (SIH26001), ResQtech addresses the challenge of regional slope failure risk by fusing machine-learning static terrain susceptibility with dynamic hydrometeorological satellite observations (NASA IMERG rainfall and NASA SMAP soil moisture).

```
DETECT → ANALYZE → ASSESS RISK → EXPLAIN → VISUALIZE → WARN → PRIORITIZE → ACKNOWLEDGE → ACT
```

---

## Key Features

- **Layer 1: Machine-Learning Static Susceptibility Engine**
  - Trained `RandomForestClassifier` (200 trees) on 30m SRTM DEM elevation/slope and GSI historical landslide spatial density.
  - Spatial block cross-validation (`GroupKFold` on 25km blocks) achieves a leakage-free spatial ROC-AUC of `0.736`.

- **Layer 2: Dynamic Hydrometeorological Trigger Engine**
  - Evaluates short-term rainfall ($R_{1d}$), 3-day accumulated rainfall ($R_{3d}$), 7-day antecedent precipitation ($R_{7d}$), and SMAP soil moisture saturation ratio ($M_{soil}$).

- **Layer 3: Risk Fusion Engine & Explainability**
  - Dynamically fuses static susceptibility and environmental pressure into a single Current Risk Index ($0 - 100$) categorized as `LOW`, `MODERATE`, `HIGH`, or `INSUFFICIENT_DATA`.
  - Automated natural language explainability narratives identifying major contributing factors.

- **Interactive Leaflet GIS Dashboard**
  - Dark-mode GIS interface displaying 15 pilot monitoring locations across NER (Assam, Sikkim, Meghalaya, Mizoram, Nagaland, Manipur, Tripura, Arunachal Pradesh).
  - Time-series risk trend visualization, layer breakdown comparison, and search filtering.

- **What-If Demo Risk Simulator**
  - Interactive scenario engine allowing operators to simulate extreme precipitation/cloudburst events and evaluate elevated risk in under 30 seconds.

- **Authority Command Center & Operational Workflow**
  - Dedicated disaster-management decision support UI featuring operational summary cards, high-risk priority queue, active warning feed, and an audit-logged workflow lifecycle (`NEW` $\rightarrow$ `ACKNOWLEDGED` $\rightarrow$ `MONITORING` $\rightarrow$ `RESPONSE_DISPATCHED` $\rightarrow$ `RESOLVED`).
  - Persistent SQLite storage (`data/alerts.db`) ensuring state continuity across restarts.

---

## Quick Start Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+

### One-Click Launch (Windows)
```cmd
scripts\start_demo.bat
```

### Manual Launch

1. **Start FastAPI Backend**:
   ```bash
   python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   *Swagger API Documentation*: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

2. **Start React GIS Dashboard**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   *GIS Dashboard*: [http://localhost:5173](http://localhost:5173)

---

## Test Suite Execution

### Backend Python Tests (pytest)
```bash
python -m pytest
```

### Frontend Production Build
```bash
cd frontend
npm run build
```

---

## Project Structure

```
ResQtech/
├── backend/                  # FastAPI backend application
│   └── app/
│       ├── api/              # REST API endpoint handlers (/api/v1)
│       ├── schemas/          # Pydantic request/response validation schemas
│       └── services/         # Risk fusion & SQLite alert services
├── data/
│   └── processed/            # Processed Parquet datasets & GeoJSON outputs
├── docs/                     # Documentation (Architecture, SIH Demo Guide, Judge Q&A)
├── frontend/                 # React 19 + Vite 8 Leaflet GIS application
├── models/
│   └── trained/              # Phase 5B trained Random Forest model (.joblib)
├── reports/                  # System audit & phase verification reports
├── scripts/                  # Data processing & startup batch scripts
├── src/                      # Core Python scientific risk pipeline
│   ├── dem/                  # Elevation & slope processing
│   ├── geo/                  # Spatial sampling & pseudo-absence control
│   ├── ml/                   # Model training & spatial cross-validation
│   └── risk/                 # Static, dynamic, and fusion engines
└── tests/                    # Backend pytest suite (73+ test cases)
```

---

## Scientific Disclaimers & Known Limitations

1. **Prototype Disclaimer**: *PROTOTYPE OPERATIONAL PARAMETERS — REQUIRES REGIONAL CALIBRATION*.
2. **Offline Data Freshness**: Operations utilize offline historical cached prototype datasets (`is_live = false`, latest valid observation date `2025-09-23`).
3. **No Exact Timing Prediction**: System evaluates spatial susceptibility and hydrometeorological pressure; it does not predict exact landslide occurrence timestamps.
4. **Future Scope**: Real-time satellite ingestion, automated SMS/email gateway integrations, and field IoT telemetry are architecturally supported for future operational deployment.

---

*ResQtech — SIH26001 Landslide Risk Monitoring Platform*
