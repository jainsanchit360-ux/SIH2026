"""FastAPI API Endpoints definitions for ResQtech."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Body

from backend.app.schemas.risk_schema import (
    SystemStatusResponse,
    LocationSchema,
    SusceptibilityResponse,
    EnvironmentResponse,
    ExplanationResponse,
    RiskRecordResponse,
    GeoJSONFeatureCollection,
    DemoSimulationRequest,
    DemoSimulationResponse,
)
from backend.app.schemas.alert_schema import (
    AlertResponse,
    AlertAcknowledgeRequest,
    AlertStatusUpdateRequest,
    AlertNoteRequest,
    AlertSummaryResponse,
)
from backend.app.services.risk_service import RiskAssessmentService
from backend.app.services.alert_service import AlertService

router = APIRouter(prefix="/api/v1", tags=["ResQtech Landslide Risk API"])

_risk_service_instance = None
_alert_service_instance = None


def get_risk_service() -> RiskAssessmentService:
    """Dependency provider for RiskAssessmentService singleton instance."""
    global _risk_service_instance
    if _risk_service_instance is None:
        _risk_service_instance = RiskAssessmentService()
    return _risk_service_instance


def get_alert_service() -> AlertService:
    """Dependency provider for AlertService singleton instance."""
    global _alert_service_instance
    if _alert_service_instance is None:
        _alert_service_instance = AlertService()
        # Automatically sync deterministic historical alerts from parquet
        risk_service = get_risk_service()
        _alert_service_instance.sync_historical_alerts(risk_service._risk_df)
    return _alert_service_instance


@router.get("/health", tags=["Health & Status"], summary="Verify API health")
def health_check():
    """Health check endpoint to verify backend operational status."""
    return {
        "status": "ok",
        "service": "ResQtech Early Warning API",
        "phase": "Phase 10 - Early Warning & Command Center Operational",
        "offline_mode": True,
    }


@router.get("/system/status", response_model=SystemStatusResponse, tags=["Health & Status"], summary="Get system status & dataset metadata")
def get_system_status(service: RiskAssessmentService = Depends(get_risk_service)):
    """Retrieve detailed system health, loaded model status, and dataset record counts."""
    return service.get_system_status()


@router.get("/locations", response_model=List[LocationSchema], tags=["Locations"], summary="List monitored pilot locations")
def get_locations(service: RiskAssessmentService = Depends(get_risk_service)):
    """Retrieve list of monitored pilot geographical locations in the North-Eastern Region (NER) of India."""
    return service.get_locations()


@router.get("/risk/latest", response_model=List[RiskRecordResponse], tags=["Risk Monitoring"], summary="Get latest risk assessment for all sites")
def get_latest_risk(service: RiskAssessmentService = Depends(get_risk_service)):
    """Retrieve latest available fused landslide risk scores for all monitored pilot sites."""
    return service.get_latest_risk()


@router.get("/risk/{site_id}", response_model=RiskRecordResponse, tags=["Risk Monitoring"], summary="Get latest risk detail for a single site")
def get_risk_by_site(site_id: str, service: RiskAssessmentService = Depends(get_risk_service)):
    """Retrieve current fused landslide risk score and drivers for a specific site_id."""
    return service.get_risk_by_site(site_id)


@router.get("/risk/{site_id}/timeseries", response_model=List[RiskRecordResponse], tags=["Risk Monitoring"], summary="Get historical risk timeseries for a site")
def get_risk_timeseries(
    site_id: str,
    start_date: Optional[str] = Query(None, description="Optional start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Optional end date filter (YYYY-MM-DD)"),
    service: RiskAssessmentService = Depends(get_risk_service),
):
    """Retrieve historical observation time series of landslide risk for a site_id with optional date range filtering."""
    return service.get_risk_timeseries(site_id, start_date=start_date, end_date=end_date)


@router.get("/environment/{site_id}", response_model=EnvironmentResponse, tags=["Environmental Pressure"], summary="Get Layer 2 dynamic environmental factors")
def get_environment_by_site(site_id: str, service: RiskAssessmentService = Depends(get_risk_service)):
    """Retrieve Layer 2 dynamic environmental trigger parameters (rainfall, soil moisture) for a site_id."""
    return service.get_environment_by_site(site_id)


@router.get("/susceptibility/{site_id}", response_model=SusceptibilityResponse, tags=["Terrain Susceptibility"], summary="Get Layer 1 static susceptibility metrics")
def get_susceptibility_by_site(site_id: str, service: RiskAssessmentService = Depends(get_risk_service)):
    """Retrieve Layer 1 static terrain susceptibility metrics, drivers, and predictors for a site_id."""
    return service.get_susceptibility_by_site(site_id)


@router.get("/explanation/{site_id}", response_model=ExplanationResponse, tags=["Explainability"], summary="Get human-readable risk explanation")
def get_explanation_by_site(site_id: str, service: RiskAssessmentService = Depends(get_risk_service)):
    """Retrieve human-readable explainability narrative and what-changed trend analysis for a site_id."""
    return service.get_explanation_by_site(site_id)


@router.get("/map/risk", response_model=GeoJSONFeatureCollection, tags=["Map Visualization"], summary="Get GeoJSON FeatureCollection for Leaflet map layer")
def get_map_risk(service: RiskAssessmentService = Depends(get_risk_service)):
    """Retrieve location risk list formatted as a standards-compliant GeoJSON FeatureCollection with [longitude, latitude] coordinates."""
    return service.get_map_risk()


@router.post("/demo/simulate", response_model=DemoSimulationResponse, tags=["Demo Simulation"], summary="Simulate what-if rainfall/soil moisture scenario")
def simulate_demo_risk(
    request: DemoSimulationRequest,
    service: RiskAssessmentService = Depends(get_risk_service),
):
    """Execute what-if demo risk simulation under simulated environmental pressure (e.g. monsoon rainfall spike)."""
    return service.simulate_demo(request)


# =====================================================================
# PHASE 10: EARLY WARNING & AUTHORITY COMMAND CENTER ENDPOINTS
# =====================================================================

@router.get("/alerts", response_model=List[AlertResponse], tags=["Early Warning Alerts"], summary="List operational alerts")
def get_alerts(
    status: Optional[str] = Query(None, description="Filter by status: NEW, ACKNOWLEDGED, MONITORING, RESPONSE_DISPATCHED, RESOLVED"),
    severity: Optional[str] = Query(None, description="Filter by severity: HIGH, MODERATE, LOW"),
    site_id: Optional[str] = Query(None, description="Filter by target site_id"),
    simulation_mode: Optional[bool] = Query(None, description="Filter by simulation_mode (true/false)"),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Retrieve filtered operational early-warning alerts."""
    return alert_service.get_alerts(
        status=status,
        severity=severity,
        site_id=site_id,
        simulation_mode=simulation_mode,
    )


@router.get("/alerts/summary", response_model=AlertSummaryResponse, tags=["Early Warning Alerts"], summary="Get Command Center summary metrics")
def get_alert_summary(alert_service: AlertService = Depends(get_alert_service)):
    """Retrieve aggregate summary counts for Authority Command Center dashboard cards."""
    return alert_service.get_alert_summary()


@router.get("/alerts/active", response_model=List[AlertResponse], tags=["Early Warning Alerts"], summary="Get active un-resolved warnings")
def get_active_alerts(alert_service: AlertService = Depends(get_alert_service)):
    """Retrieve active warnings requiring authority attention."""
    return alert_service.get_active_alerts()


@router.get("/alerts/history", response_model=List[AlertResponse], tags=["Early Warning Alerts"], summary="Get alert history log")
def get_alert_history(alert_service: AlertService = Depends(get_alert_service)):
    """Retrieve complete chronological alert history log."""
    return alert_service.get_alert_history()


@router.get("/alerts/{alert_id}", response_model=AlertResponse, tags=["Early Warning Alerts"], summary="Get alert detail by alert_id")
def get_alert_by_id(alert_id: str, alert_service: AlertService = Depends(get_alert_service)):
    """Retrieve single alert detail by alert_id."""
    return alert_service.get_alert_by_id(alert_id)


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse, tags=["Early Warning Alerts"], summary="Acknowledge an alert")
def acknowledge_alert(
    alert_id: str,
    payload: AlertAcknowledgeRequest = Body(...),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Transition alert from NEW to ACKNOWLEDGED state."""
    return alert_service.acknowledge_alert(
        alert_id=alert_id,
        acknowledged_by=payload.acknowledged_by or "District Control Room",
    )


@router.patch("/alerts/{alert_id}/status", response_model=AlertResponse, tags=["Early Warning Alerts"], summary="Update alert workflow status")
def update_alert_status(
    alert_id: str,
    payload: AlertStatusUpdateRequest = Body(...),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Update alert status with strict workflow state machine validation (e.g. ACKNOWLEDGED -> MONITORING -> RESOLVED)."""
    return alert_service.update_alert_status(
        alert_id=alert_id,
        new_status=payload.new_status,
        performed_by=payload.performed_by or "Authority Officer",
        note=payload.reason_or_note,
    )


@router.post("/alerts/{alert_id}/notes", response_model=AlertResponse, tags=["Early Warning Alerts"], summary="Add operational response note")
def add_alert_note(
    alert_id: str,
    payload: AlertNoteRequest = Body(...),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Add an operational response note to an alert."""
    return alert_service.add_response_note(
        alert_id=alert_id,
        note_text=payload.note,
        author=payload.author or "Authority Officer",
    )


@router.post("/demo/simulate-and-alert", response_model=AlertResponse, tags=["Demo Simulation"], summary="Run demo simulation and generate operational alert")
def simulate_and_create_alert(
    request: DemoSimulationRequest,
    risk_service: RiskAssessmentService = Depends(get_risk_service),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Execute what-if demo risk simulation AND automatically create a SIMULATED_DEMO operational warning."""
    sim_res = risk_service.simulate_demo(request)
    sim_dict = sim_res.model_dump()
    sim_dict["simulated_rainfall_1d"] = request.simulated_rainfall_1d
    sim_dict["simulated_rainfall_3d"] = request.simulated_rainfall_3d
    sim_dict["simulated_rainfall_7d"] = request.simulated_rainfall_7d
    sim_dict["simulated_soil_moisture"] = request.simulated_soil_moisture

    sim_alert = alert_service.create_simulated_alert(sim_dict)
    return sim_alert


@router.post("/demo/reset", tags=["Demo Simulation"], summary="Reset simulated demo alerts")
def reset_demo_alerts(alert_service: AlertService = Depends(get_alert_service)):
    """Purge simulated operational alert records from SQLite DB while keeping scientific Parquet datasets 100% untouched."""
    deleted_count = alert_service.reset_demo_alerts()
    return {
        "status": "ok",
        "message": f"Successfully reset {deleted_count} simulated demo operational alert records.",
        "deleted_count": deleted_count,
        "scientific_datasets_mutated": False,
    }
