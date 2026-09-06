"""Pydantic data validation models for Landslide Risk API endpoints."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


CALIBRATION_DISCLAIMER_TEXT = (
    "PROTOTYPE OPERATIONAL PARAMETERS — REQUIRES REGIONAL CALIBRATION"
)


class SystemStatusResponse(BaseModel):
    """Response payload for system status and environment health."""

    status: str = "OPERATIONAL"
    service_status: str = "OPERATIONAL"
    app_name: str = "ResQtech"
    api_version: str = "0.1.0-prototype"
    model_status: str = "LOADED"
    model_version: str = "1.1.0-phase5b"
    processed_data_status: str = "AVAILABLE"
    environmental_dataset_status: str = "OFFLINE_CACHE_AVAILABLE"
    last_available_observation_date: str = "2025-09-23"
    latest_environmental_observation_date: str = "2025-09-30"
    latest_valid_risk_observation_date: str = "2025-09-23"
    dataset_generated_at: str = "2026-09-06"
    offline_mode: bool = True
    is_live: bool = False
    region: str = "North-Eastern Region (NER) India"
    model_features: List[str] = Field(
        default_factory=lambda: [
            "elevation_m",
            "slope_deg",
            "historical_count_5km",
            "historical_count_10km",
        ]
    )
    dataset_records: Dict[str, int] = Field(default_factory=dict)
    dataset_update_timestamp: Optional[str] = None
    calibration_disclaimer: str = CALIBRATION_DISCLAIMER_TEXT


class LocationSchema(BaseModel):
    """Schema representing a monitored geographical site/location."""

    site_id: str
    site_name: str
    state: str
    district: Optional[str] = "NER"
    latitude: float
    longitude: float


class SusceptibilityResponse(BaseModel):
    """Schema for Layer 1 static susceptibility metrics."""

    site_id: Optional[str] = None
    site_name: Optional[str] = None
    latitude: float
    longitude: float
    static_susceptibility_score: float = Field(..., ge=0.0, le=100.0, description="Static susceptibility index [0-100]")
    static_susceptibility_level: str = Field(..., description="LOW, MODERATE, or HIGH ranking")
    static_model_version: str
    elevation_m: Optional[float] = None
    slope_deg: Optional[float] = None
    historical_count_5km: Optional[float] = None
    historical_count_10km: Optional[float] = None
    static_major_factors: List[str] = Field(default_factory=list)
    features_input: Dict[str, Any] = Field(default_factory=dict)
    data_status: str = "VALID"
    calibration_disclaimer: str = CALIBRATION_DISCLAIMER_TEXT


class EnvironmentResponse(BaseModel):
    """Schema for Layer 2 dynamic environmental trigger metrics."""

    site_id: str
    site_name: str
    observation_date: str
    data_status: str = Field("VALID", description="VALID, PARTIAL_RAINFALL_ONLY, or INSUFFICIENT_DATA")
    rainfall_1d: Optional[float] = None
    rainfall_3d: Optional[float] = None
    rainfall_7d: Optional[float] = None
    soil_moisture: Optional[float] = None
    dynamic_trigger_score: float = Field(..., ge=0.0, le=100.0)
    dynamic_trigger_level: str
    major_trigger_factors: List[str] = Field(default_factory=list)
    source_provenance: str = "NASA IMERG + NASA SMAP L3"
    calibration_disclaimer: str = CALIBRATION_DISCLAIMER_TEXT


class ExplanationResponse(BaseModel):
    """Schema for explainability and what-changed narrative."""

    site_id: str
    site_name: str
    current_risk_score: float
    current_risk_level: str
    previous_risk_score: Optional[float] = None
    risk_score_change: Optional[float] = None
    risk_trend: str = "UNKNOWN"
    major_risk_factors: List[str] = Field(default_factory=list)
    static_contributors: List[str] = Field(default_factory=list)
    dynamic_contributors: List[str] = Field(default_factory=list)
    risk_explanation: str
    what_changed: str
    calibration_disclaimer: str = CALIBRATION_DISCLAIMER_TEXT


class RiskRecordResponse(BaseModel):
    """Response schema representing fused current landslide risk assessment."""

    site_id: str
    site_name: str
    state: str
    district: Optional[str] = "NER"
    latitude: float
    longitude: float
    observation_date: str
    freshness_status: str = "OFFLINE_HISTORICAL_CACHE"
    is_live: bool = False
    
    static_susceptibility_score: float = Field(..., ge=0.0, le=100.0)
    static_susceptibility_level: str
    elevation_m: Optional[float] = None
    slope_deg: Optional[float] = None
    historical_count_5km: Optional[float] = None
    historical_count_10km: Optional[float] = None
    
    rainfall_1d: Optional[float] = None
    rainfall_3d: Optional[float] = None
    rainfall_7d: Optional[float] = None
    soil_moisture: Optional[float] = None
    dynamic_trigger_score: float = Field(..., ge=0.0, le=100.0)
    dynamic_trigger_level: str

    current_risk_score: float = Field(..., ge=0.0, le=100.0)
    current_risk_level: str
    previous_risk_score: Optional[float] = None
    risk_score_change: Optional[float] = None
    risk_trend: str = "UNKNOWN"

    major_risk_factors: List[str] = Field(default_factory=list)
    static_contributors: List[str] = Field(default_factory=list)
    dynamic_contributors: List[str] = Field(default_factory=list)
    risk_explanation: str
    what_changed: str

    data_completeness: Dict[str, Any] = Field(default_factory=dict)
    data_status: str = "VALID"
    source_provenance: str = "NASA IMERG + NASA SMAP L3"
    simulation_mode: bool = False
    data_source: str = "REAL_OBSERVED_PROCESSED"
    calibration_disclaimer: str = CALIBRATION_DISCLAIMER_TEXT


class GeoJSONGeometry(BaseModel):
    """GeoJSON Geometry Object (Point longitude, latitude)."""

    type: str = "Point"
    coordinates: List[float] = Field(..., description="[longitude, latitude] array in WGS84 EPSG:4326")


class GeoJSONFeature(BaseModel):
    """GeoJSON Feature Object."""

    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection Object for Leaflet/GIS map integration."""

    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]


class DemoSimulationRequest(BaseModel):
    """Request body payload for demo what-if risk simulation."""

    site_id: Optional[str] = Field(None, description="Optional target site_id (defaults to pilot site)")
    latitude: Optional[float] = Field(None, ge=21.0, le=30.0, description="Optional custom latitude")
    longitude: Optional[float] = Field(None, ge=87.0, le=98.0, description="Optional custom longitude")
    simulated_rainfall_1d: float = Field(..., ge=0.0, le=500.0, description="Simulated 1-day rainfall accumulation in mm/day (>= 0)")
    simulated_rainfall_3d: float = Field(..., ge=0.0, le=1000.0, description="Simulated 3-day rainfall accumulation in mm (>= 0)")
    simulated_rainfall_7d: float = Field(..., ge=0.0, le=2000.0, description="Simulated 7-day rainfall accumulation in mm (>= 0)")
    simulated_soil_moisture: float = Field(..., ge=0.0, le=1.0, description="Simulated volumetric soil moisture (0.0 to 1.0 or %)")
    scenario_name: str = Field("Heavy Monsoon Downpour Simulation", description="Descriptive scenario label")


class DemoSimulationResponse(RiskRecordResponse):
    """Response model for demo simulation assessment."""

    scenario_name: str
    baseline_current_risk_score: Optional[float] = None
    baseline_current_risk_level: Optional[str] = None
    simulated_current_risk_score: float = Field(..., ge=0.0, le=100.0)
    simulated_current_risk_level: str
