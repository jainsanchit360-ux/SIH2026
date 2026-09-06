# ResQtech (SIH26001) — 3-Minute SIH Demo Presentation Guide

## Demo Setup (Pre-Presentation)
1. Double-click `scripts/start_demo.bat` (or start backend `uvicorn backend.app.main:app --port 8000` and frontend `npm run dev`).
2. Open browser to `http://localhost:5173`.
3. Ensure backend indicates `CONNECTED` (green badge in header).

---

## 3-Minute Script Step-by-Step

### 1. Introduction & GIS Overview (0:00 - 0:45)
- **Action**: Show main split-screen dashboard displaying 15 pilot monitoring locations across North-Eastern Region (NER) India on Leaflet GIS map.
- **Presenter Dialogue**:
  > *"ResQtech is an AI-driven Early Warning and Landslide Risk Monitoring System specifically designed for the complex topography of India's North-Eastern Region (Problem Statement SIH26001).*
  > *Rather than relying on static hazard maps or single rain gauges, ResQtech fuses machine-learning static terrain susceptibility with dynamic NASA satellite rainfall and soil moisture pressure."*

### 2. Location Intelligence & Static vs Dynamic Fusion (0:45 - 1:30)
- **Action**: Click location `GSI_SITE_01` (Hailakandi, Assam) or `NER_PILOT_01` (Gangtok, Sikkim) in search list.
- **Presenter Dialogue**:
  > *"When we select a monitored site, the system breaks down the risk into two distinct scientific layers:*
  > *First, Layer 1: Static Susceptibility Score based on Random Forest analysis of SRTM elevation, slope, and historical GSI landslide spatial density.*
  > *Second, Layer 2: Dynamic Trigger Score incorporating NASA IMERG precipitation and SMAP soil moisture saturation.*
  > *Notice that all historical dataset values display clear observation timestamps (2025-09-23) to preserve scientific integrity."*

### 3. What-If Cloudburst Simulation & Alert Triggering (1:30 - 2:15)
- **Action**: Scroll down to **WHAT-IF DEMO RISK SIMULATOR**. Set 24h rainfall to `185 mm/day` and soil moisture to `82%`. Click **Execute What-If Scenario**.
- **Presenter Dialogue**:
  > *"During extreme weather events, disaster management authorities need to evaluate incoming meteorological forecasts.*
  > *Using our What-If simulator, we simulate a cloudburst event. The fusion engine calculates an immediate surge in dynamic trigger pressure to 88.4/100, elevating the site's fused risk from MODERATE (58) to HIGH (73).*
  > *Notice that a prototype operational warning is automatically generated and pushed to our Command Center queue—without mutating underlying baseline historical datasets."*

### 4. Authority Command Center & Response Workflow (2:15 - 3:00)
- **Action**: Click **AUTHORITY COMMAND CENTER** tab in header navigation. Point out summary metric cards and active warnings feed.
- **Presenter Dialogue**:
  > *"We now switch to the Authority Command Center. Here, district control room operators receive high-priority active warnings ranked in a real-time priority queue.*
  > *The operator clicks 'Acknowledge' on the alert, changing status from NEW to ACKNOWLEDGED.*
  > *The officer opens the alert drawer, adds an operational note—'Field teams dispatched to monitor Hailakandi route'—and updates workflow status to 'RESPONSE DISPATCHED'.*
  > *Every status transition is logged with immutable timestamps in our persistent SQLite audit store."*

---

## Failure Recovery Instructions

| Issue | Cause | Recovery Action |
|-------|-------|-----------------|
| **Backend Disconnected** | Uvicorn server stopped | Run `scripts/start_backend.bat` or `python -m uvicorn backend.app.main:app --port 8000`. Click "Retry Connection" banner. |
| **Map Basemap Blank** | Offline/No Internet for CartoDB tiles | Map view gracefully falls back to grid presentation; all site lists, risk metrics, charts, and Command Center workflow remain 100% operational. |
| **Alerts Already Exist** | Previous demo session stored state | Click **RESET DEMO ALERTS** button in Command Center header to restore clean state. |
