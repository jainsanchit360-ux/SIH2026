"""Pydantic data validation models for Phase 10 Alerting & Authority Command Center."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

PROTOTYPE_WARNING_DISCLAIMER = (
    "PROTOTYPE OPERATIONAL WARNING — REQUIRES REGIONAL CALIBRATION"
)


class ResponseNoteItem(BaseModel):
    """Single operational response note log item."""

    timestamp: str
    note: str
    author: Optional[str] = "Authority Officer"


class StatusAuditItem(BaseModel):
    """Workflow state transition audit record."""

    timestamp: str
    from_status: str
    to_status: str
    performed_by: Optional[str] = "System/Operator"


class AlertResponse(BaseModel):
    """Response schema representing an operational early-warning alert."""

    alert_id: str = Field(..., description="Unique deterministic alert ID e.g. ALT-20250923-GSI_SITE_01-HIGH")
    site_id: str
    site_name: str
    state: str
    district: Optional[str] = "NER"
    latitude: float
    longitude: float

    created_at: str
    updated_at: str
    observation_date: str

    risk_score: float = Field(..., ge=0.0, le=100.0, description="Fused current landslide risk score index")
    risk_level: str = Field(..., description="HIGH, MODERATE, LOW, or INSUFFICIENT_DATA")
    severity: str = Field(..., description="Operational warning severity: HIGH, MODERATE, LOW")

    static_susceptibility_score: Optional[float] = None
    dynamic_trigger_score: Optional[float] = None

    rainfall_1d: Optional[float] = None
    rainfall_3d: Optional[float] = None
    rainfall_7d: Optional[float] = None
    soil_moisture: Optional[float] = None

    reason: str
    major_risk_factors: List[str] = Field(default_factory=list)
    risk_explanation: Optional[str] = None
    what_changed: Optional[str] = None

    data_source: str = Field("OFFLINE_HISTORICAL_CACHE", description="OFFLINE_HISTORICAL_CACHE or SIMULATED_DEMO")
    simulation_mode: bool = False

    status: str = Field("NEW", description="NEW, ACKNOWLEDGED, MONITORING, RESPONSE_DISPATCHED, RESOLVED")

    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None

    response_notes: List[ResponseNoteItem] = Field(default_factory=list)
    audit_history: List[StatusAuditItem] = Field(default_factory=list)

    calibration_disclaimer: str = PROTOTYPE_WARNING_DISCLAIMER


class AlertAcknowledgeRequest(BaseModel):
    """Request payload to acknowledge an alert."""

    acknowledged_by: Optional[str] = Field("District Control Room Operator", description="Operator name or title acknowledging the alert")


class AlertStatusUpdateRequest(BaseModel):
    """Request payload to update alert workflow status."""

    new_status: str = Field(..., description="Target status: ACKNOWLEDGED, MONITORING, RESPONSE_DISPATCHED, or RESOLVED")
    performed_by: Optional[str] = Field("Authority Operator", description="Operator executing the state transition")
    reason_or_note: Optional[str] = Field(None, description="Optional note associated with status update")


class AlertNoteRequest(BaseModel):
    """Request payload to add an operational note to an alert."""

    note: str = Field(..., min_length=1, max_length=1000, description="Operational response note text")
    author: Optional[str] = Field("District Control Room", description="Author of the note")


class AlertSummaryResponse(BaseModel):
    """Summary counter metrics for Authority Command Center dashboard."""

    active_warnings_count: int = 0
    unacknowledged_alerts_count: int = 0
    high_risk_sites_count: int = 0
    moderate_risk_sites_count: int = 0
    response_dispatched_count: int = 0
    resolved_count: int = 0
    insufficient_data_sites_count: int = 0
    simulated_alerts_count: int = 0
    last_updated_at: str
    calibration_disclaimer: str = PROTOTYPE_WARNING_DISCLAIMER
