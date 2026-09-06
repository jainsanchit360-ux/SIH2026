# ResQtech (SIH26001) System Architecture

## Overview

ResQtech is an AI-based Early Warning and Landslide Risk Monitoring System specifically designed for the North-Eastern Region (NER) of India. The architecture combines a two-layer scientific risk fusion methodology with a modern web GIS application and operational Authority Command Center.

```mermaid
flowchart TD
    subgraph Data Layer
        A1[GSI Historical Landslide Inventory]
        A2[SRTM 30m DEM Elevation & Slope]
        A3[NASA IMERG 0.1° Precipitation]
        A4[NASA SMAP 0.1° Soil Moisture]
    end

    subgraph Scientific Processing Pipeline
        B1[Spatial Sampling & Pseudo-Absence Generation]
        B2[Layer 1: Static Susceptibility Engine]
        B3[Layer 2: Dynamic Trigger Engine]
        B4[Phase 7 Risk Fusion Engine]
    end

    subgraph Backend API (FastAPI)
        C1[FastAPI REST API v0.1.0-prototype]
        C2[SQLite Alert Store data/alerts.db]
        C3[What-If Demo Simulator]
    end

    subgraph Frontend (React + Leaflet)
        D1[Leaflet GIS Dashboard]
        D2[Location Intelligence Panel]
        D3[Explainability & Trend Analytics]
        D4[Authority Command Center]
    end

    A1 --> B1
    A2 --> B1
    B1 --> B2
    A3 --> B3
    A4 --> B3
    B2 --> B4
    B3 --> B4
    B4 --> C1
    C2 <--> C1
    C3 <--> C1
    C1 --> D1
    C1 --> D2
    C1 --> D3
    C1 --> D4
```

## Layered Risk Methodology

### Layer 1: Static Terrain Susceptibility
- **Model**: `RandomForestClassifier` (200 estimators, GroupKFold spatial cross-validation AUC ~0.736)
- **Features**: `elevation_m`, `slope_deg`, `historical_count_5km`, `historical_count_10km`
- **Output**: Static Susceptibility Score $S \in [0, 100]$ representing baseline geological/terrain predisposition.

### Layer 2: Dynamic Hydrometeorological Trigger
- **Inputs**: 24h precipitation ($R_{1d}$), 3-day accumulated rainfall ($R_{3d}$), 7-day accumulated rainfall ($R_{7d}$), and soil moisture saturation ratio ($M_{soil}$).
- **Output**: Dynamic Trigger Score $D \in [0, 100]$ representing transient environmental pressure.

### Layer 3: Risk Fusion Engine
- **Formula**: $Risk = w_s \cdot S + w_d \cdot D$ where $w_s = 0.40$ and $w_d = 0.60$ under high trigger conditions.
- **Risk Level Categorization**:
  - **LOW**: $Risk < 40.0$
  - **MODERATE**: $40.0 \le Risk < 70.0$
  - **HIGH**: $Risk \ge 70.0$
  - **INSUFFICIENT_DATA**: Missing environmental parameters.

## Storage & Operational State

- **Scientific Datasets**: Immutable Apache Parquet files stored in `data/processed/`.
- **Operational Alerts**: SQLite database at `data/alerts.db` managed via Python standard `sqlite3` module.

## Workflow Enums

- **NEW** $\rightarrow$ **ACKNOWLEDGED**
- **ACKNOWLEDGED** $\rightarrow$ **MONITORING** or **RESPONSE_DISPATCHED**
- **MONITORING** $\rightarrow$ **RESPONSE_DISPATCHED** or **RESOLVED**
- **RESPONSE_DISPATCHED** $\rightarrow$ **RESOLVED**

---

> **Scientific Disclaimer**: *PROTOTYPE OPERATIONAL PARAMETERS — REQUIRES REGIONAL CALIBRATION*.
