"""Landslide Risk Assessment Service for ResQtech.

Orchestrates calls to Layer 1 Static Susceptibility, Layer 2 Dynamic Trigger Engine,
Risk Fusion Engine, and Demo Simulation using cached processed datasets offline.
"""

import math
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
from fastapi import HTTPException

from backend.app.core.config import settings, API_VERSION
from backend.app.schemas.risk_schema import (
    SystemStatusResponse,
    LocationSchema,
    SusceptibilityResponse,
    EnvironmentResponse,
    ExplanationResponse,
    RiskRecordResponse,
    GeoJSONGeometry,
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    DemoSimulationRequest,
    DemoSimulationResponse,
)
from src.risk.susceptibility import StaticSusceptibilityEngine
from src.risk.trigger_engine import DynamicTriggerEngine
from src.risk.risk_fusion import RiskFusionEngine
from src.risk.demo_simulation import simulate_dynamic_risk_scenario

logger = logging.getLogger(__name__)


def _sanitize_float(val: Any) -> Optional[float]:
    """Helper to convert float values, turning NaN/Inf into None for JSON safety."""
    if val is None or pd.isna(val):
        return None
    try:
        f_val = float(val)
        if math.isnan(f_val) or math.isinf(f_val):
            return None
        return round(f_val, 2)
    except (ValueError, TypeError):
        return None


def _clean_str(val: Any, default: str = "") -> str:
    """Helper to convert string values safely."""
    if val is None or pd.isna(val):
        return default
    return str(val).strip()


def _clean_list(val: Any) -> List[str]:
    """Helper to ensure output is a clean list of strings."""
    if isinstance(val, (list, np.ndarray)):
        return [str(x) for x in val if x and not pd.isna(x)]
    elif isinstance(val, str) and val:
        return [val]
    return []


class RiskAssessmentService:
    """Service class connecting Phase 7 intelligence and offline processed datasets."""

    def __init__(self):
        self.settings = settings
        self.susceptibility_engine = StaticSusceptibilityEngine()
        self.trigger_engine = DynamicTriggerEngine()
        self.fusion_engine = RiskFusionEngine()

        self._risk_df: Optional[pd.DataFrame] = None
        self._env_df: Optional[pd.DataFrame] = None
        self._cache_df: Optional[pd.DataFrame] = None
        self._load_datasets()

    def _load_datasets(self):
        """Load offline processed datasets into memory ONCE at service initialization."""
        try:
            risk_file = self.settings.DATA_PROCESSED_DIR / "current_landslide_risk.parquet"
            if risk_file.exists():
                self._risk_df = pd.read_parquet(risk_file)
                logger.info(f"Loaded {len(self._risk_df)} records from {risk_file}")
            else:
                logger.warning(f"Risk parquet file not found at {risk_file}")

            env_file = self.settings.DATA_PROCESSED_DIR / "dynamic_environmental_features.parquet"
            if env_file.exists():
                self._env_df = pd.read_parquet(env_file)
                logger.info(f"Loaded {len(self._env_df)} records from {env_file}")

            cache_file = self.settings.DATA_PROCESSED_DIR / "demo_dynamic_environmental_cache.parquet"
            if cache_file.exists():
                self._cache_df = pd.read_parquet(cache_file)
                logger.info(f"Loaded {len(self._cache_df)} records from {cache_file}")
        except Exception as e:
            logger.error(f"Error loading backend processed datasets: {e}")

    def get_system_status(self) -> SystemStatusResponse:
        """Retrieve operational system status and dataset metadata."""
        record_counts = {}
        latest_env_date = "2025-09-30"
        latest_valid_risk_date = "2025-09-23"

        if self._env_df is not None and not self._env_df.empty:
            record_counts["dynamic_environmental_features"] = len(self._env_df)
            if "observation_date" in self._env_df.columns:
                env_dates = self._env_df["observation_date"].dropna().astype(str).tolist()
                if env_dates:
                    latest_env_date = max(env_dates)

        if self._risk_df is not None and not self._risk_df.empty:
            record_counts["current_landslide_risk"] = len(self._risk_df)
            if "observation_date" in self._risk_df.columns and "current_risk_score" in self._risk_df.columns:
                valid_risk_df = self._risk_df[self._risk_df["current_risk_score"].notna()]
                valid_dates = valid_risk_df["observation_date"].dropna().astype(str).tolist()
                if valid_dates:
                    latest_valid_risk_date = max(valid_dates)

        if self._cache_df is not None and not self._cache_df.empty:
            record_counts["demo_dynamic_environmental_cache"] = len(self._cache_df)

        return SystemStatusResponse(
            status="OPERATIONAL",
            service_status="OPERATIONAL",
            app_name=self.settings.APP_NAME,
            api_version=API_VERSION,
            model_status="LOADED",
            model_version=self.susceptibility_engine.model_version,
            processed_data_status="AVAILABLE",
            environmental_dataset_status="OFFLINE_CACHE_AVAILABLE",
            last_available_observation_date=latest_valid_risk_date,
            latest_environmental_observation_date=latest_env_date,
            latest_valid_risk_observation_date=latest_valid_risk_date,
            dataset_generated_at="2026-09-06",
            offline_mode=True,
            is_live=False,
            region="North-Eastern Region (NER) India",
            model_features=self.susceptibility_engine.feature_names,
            dataset_records=record_counts,
            dataset_update_timestamp="2026-09-06",
        )

    def get_locations(self) -> List[LocationSchema]:
        """Retrieve list of monitored pilot/geographical locations."""
        if self._risk_df is None or self._risk_df.empty:
            return []

        unique_sites = self._risk_df.drop_duplicates(subset=["site_id"])
        locations = []
        for _, row in unique_sites.iterrows():
            locations.append(
                LocationSchema(
                    site_id=_clean_str(row.get("site_id", row.get("location_id", "UNKNOWN"))),
                    site_name=_clean_str(row.get("site_name", "Monitored Site")),
                    state=_clean_str(row.get("state", "NER")),
                    district=_clean_str(row.get("district", "NER")),
                    latitude=float(row.get("latitude")),
                    longitude=float(row.get("longitude")),
                )
            )
        return locations

    def _row_to_risk_record(self, row: pd.Series) -> RiskRecordResponse:
        """Convert a dataframe row into a validated, NaN-safe RiskRecordResponse."""
        score = _sanitize_float(row.get("current_risk_score")) or 0.0
        sus_score = _sanitize_float(row.get("static_susceptibility_score")) or 0.0
        trig_score = _sanitize_float(row.get("dynamic_trigger_score")) or 0.0

        return RiskRecordResponse(
            site_id=_clean_str(row.get("site_id", row.get("location_id", "SITE_01"))),
            site_name=_clean_str(row.get("site_name", "Monitored Site")),
            state=_clean_str(row.get("state", "NER")),
            district=_clean_str(row.get("district", "NER")),
            latitude=float(row.get("latitude")),
            longitude=float(row.get("longitude")),
            observation_date=_clean_str(row.get("observation_date")),
            freshness_status="OFFLINE_HISTORICAL_CACHE",
            is_live=False,
            
            static_susceptibility_score=sus_score,
            static_susceptibility_level=_clean_str(row.get("static_susceptibility_level"), "LOW"),
            elevation_m=_sanitize_float(row.get("elevation_m")),
            slope_deg=_sanitize_float(row.get("slope_deg")),
            historical_count_5km=_sanitize_float(row.get("historical_count_5km")),
            historical_count_10km=_sanitize_float(row.get("historical_count_10km")),

            rainfall_1d=_sanitize_float(row.get("rainfall_1d")),
            rainfall_3d=_sanitize_float(row.get("rainfall_3d")),
            rainfall_7d=_sanitize_float(row.get("rainfall_7d")),
            soil_moisture=_sanitize_float(row.get("soil_moisture")),
            dynamic_trigger_score=trig_score,
            dynamic_trigger_level=_clean_str(row.get("dynamic_trigger_level"), "LOW"),

            current_risk_score=score,
            current_risk_level=_clean_str(row.get("current_risk_level"), "LOW"),
            previous_risk_score=_sanitize_float(row.get("previous_risk_score")),
            risk_score_change=_sanitize_float(row.get("risk_score_change")),
            risk_trend=_clean_str(row.get("risk_trend"), "UNKNOWN"),

            major_risk_factors=_clean_list(row.get("major_risk_factors")),
            static_contributors=_clean_list(row.get("static_contributors")),
            dynamic_contributors=_clean_list(row.get("dynamic_contributors")),
            risk_explanation=_clean_str(row.get("risk_explanation")),
            what_changed=_clean_str(row.get("what_changed")),

            data_completeness=dict(row.get("data_completeness")) if isinstance(row.get("data_completeness"), dict) else {},
            data_status=_clean_str(row.get("data_status"), "VALID"),
            source_provenance=_clean_str(row.get("source_provenance"), "NASA IMERG + NASA SMAP L3"),
            simulation_mode=bool(row.get("simulation_mode", False)),
            data_source=_clean_str(row.get("data_source"), "REAL_OBSERVED_PROCESSED"),
        )

    def get_latest_risk(self) -> List[RiskRecordResponse]:
        """Retrieve latest current risk records for all sites."""
        if self._risk_df is None or self._risk_df.empty:
            return []

        df_sorted = self._risk_df.sort_values(by="observation_date", ascending=False)
        latest_df = df_sorted.drop_duplicates(subset=["site_id"])
        
        return [self._row_to_risk_record(row) for _, row in latest_df.iterrows()]

    def get_risk_by_site(self, site_id: str) -> RiskRecordResponse:
        """Retrieve latest risk record for a specific site_id."""
        if self._risk_df is None or self._risk_df.empty:
            raise HTTPException(status_code=404, detail="Processed risk dataset unavailable")

        site_df = self._risk_df[self._risk_df["site_id"] == site_id]
        if site_df.empty:
            raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

        latest_row = site_df.sort_values(by="observation_date", ascending=False).iloc[0]
        return self._row_to_risk_record(latest_row)

    def get_risk_timeseries(
        self,
        site_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[RiskRecordResponse]:
        """Retrieve chronological timeseries of risk records for a site_id with optional date filtering."""
        if self._risk_df is None or self._risk_df.empty:
            raise HTTPException(status_code=404, detail="Processed risk dataset unavailable")

        site_df = self._risk_df[self._risk_df["site_id"] == site_id]
        if site_df.empty:
            raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

        # Date filtering
        if start_date:
            site_df = site_df[site_df["observation_date"] >= start_date]
        if end_date:
            site_df = site_df[site_df["observation_date"] <= end_date]

        if site_df.empty:
            return []

        # Sort chronologically & deduplicate
        ts_sorted = site_df.drop_duplicates(subset=["observation_date"]).sort_values(by="observation_date", ascending=True)
        return [self._row_to_risk_record(row) for _, row in ts_sorted.iterrows()]

    def get_environment_by_site(self, site_id: str) -> EnvironmentResponse:
        """Retrieve dynamic environmental factors for a site_id."""
        rec = self.get_risk_by_site(site_id)
        
        # QC status classification
        if rec.rainfall_1d is None:
            data_status = "INSUFFICIENT_DATA"
        elif rec.soil_moisture is None:
            data_status = "PARTIAL_RAINFALL_ONLY"
        else:
            data_status = "VALID"

        return EnvironmentResponse(
            site_id=rec.site_id,
            site_name=rec.site_name,
            observation_date=rec.observation_date,
            data_status=data_status,
            rainfall_1d=rec.rainfall_1d,
            rainfall_3d=rec.rainfall_3d,
            rainfall_7d=rec.rainfall_7d,
            soil_moisture=rec.soil_moisture,
            dynamic_trigger_score=rec.dynamic_trigger_score,
            dynamic_trigger_level=rec.dynamic_trigger_level,
            major_trigger_factors=rec.dynamic_contributors,
            source_provenance=rec.source_provenance,
        )

    def get_susceptibility_by_site(self, site_id: str) -> SusceptibilityResponse:
        """Retrieve Layer 1 static susceptibility metrics for a site_id."""
        rec = self.get_risk_by_site(site_id)
        
        sus_eval = self.susceptibility_engine.evaluate_static_susceptibility(
            latitude=rec.latitude,
            longitude=rec.longitude,
            elevation_m=rec.elevation_m or 1250.0,
            slope_deg=rec.slope_deg or 28.5,
            historical_count_5km=rec.historical_count_5km or 4.0,
            historical_count_10km=rec.historical_count_10km or 12.0,
        )

        return SusceptibilityResponse(
            site_id=rec.site_id,
            site_name=rec.site_name,
            latitude=rec.latitude,
            longitude=rec.longitude,
            static_susceptibility_score=rec.static_susceptibility_score,
            static_susceptibility_level=rec.static_susceptibility_level,
            static_model_version=self.susceptibility_engine.model_version,
            elevation_m=rec.elevation_m,
            slope_deg=rec.slope_deg,
            historical_count_5km=rec.historical_count_5km,
            historical_count_10km=rec.historical_count_10km,
            static_major_factors=rec.static_contributors or sus_eval.get("static_major_factors", []),
            features_input=sus_eval.get("static_model_features", {}),
            data_status="VALID",
        )

    def get_explanation_by_site(self, site_id: str) -> ExplanationResponse:
        """Retrieve explainability details for a site_id."""
        rec = self.get_risk_by_site(site_id)
        return ExplanationResponse(
            site_id=rec.site_id,
            site_name=rec.site_name,
            current_risk_score=rec.current_risk_score,
            current_risk_level=rec.current_risk_level,
            previous_risk_score=rec.previous_risk_score,
            risk_score_change=rec.risk_score_change,
            risk_trend=rec.risk_trend,
            major_risk_factors=rec.major_risk_factors,
            static_contributors=rec.static_contributors,
            dynamic_contributors=rec.dynamic_contributors,
            risk_explanation=rec.risk_explanation,
            what_changed=rec.what_changed,
        )

    def get_map_risk(self) -> GeoJSONFeatureCollection:
        """Retrieve latest risk list formatted as a standards-compliant GeoJSON FeatureCollection."""
        latest_records = self.get_latest_risk()
        features = []

        for rec in latest_records:
            # Enforce GeoJSON coordinate ordering: [longitude, latitude]
            geom = GeoJSONGeometry(
                type="Point",
                coordinates=[rec.longitude, rec.latitude]
            )
            
            props = {
                "site_id": rec.site_id,
                "site_name": rec.site_name,
                "state": rec.state,
                "district": rec.district,
                "current_risk_score": rec.current_risk_score,
                "current_risk_level": rec.current_risk_level,
                "static_susceptibility_score": rec.static_susceptibility_score,
                "static_susceptibility_level": rec.static_susceptibility_level,
                "dynamic_trigger_score": rec.dynamic_trigger_score,
                "dynamic_trigger_level": rec.dynamic_trigger_level,
                "observation_date": rec.observation_date,
                "major_risk_factors": rec.major_risk_factors,
                "data_status": rec.data_status,
                "data_source": rec.data_source,
                "freshness_status": rec.freshness_status,
                "is_live": rec.is_live,
                "calibration_disclaimer": rec.calibration_disclaimer,
            }

            features.append(GeoJSONFeature(type="Feature", geometry=geom, properties=props))

        return GeoJSONFeatureCollection(type="FeatureCollection", features=features)

    def simulate_demo(self, request: DemoSimulationRequest) -> DemoSimulationResponse:
        """Execute what-if demo risk simulation under simulated environmental pressure."""
        # Input validation
        if request.simulated_rainfall_1d < 0 or request.simulated_rainfall_3d < 0 or request.simulated_rainfall_7d < 0:
            raise HTTPException(status_code=422, detail="Simulated rainfall values cannot be negative")

        sm_val = request.simulated_soil_moisture
        if sm_val > 1.0:
            if sm_val <= 100.0:
                sm_val = sm_val / 100.0
            else:
                raise HTTPException(status_code=422, detail="Soil moisture percentage must be between 0 and 100%")

        if sm_val < 0.0 or sm_val > 1.0:
            raise HTTPException(status_code=422, detail="Soil moisture fraction must be between 0.0 and 1.0")

        # Retrieve target baseline record
        baseline_record = {}
        if request.site_id:
            try:
                rec = self.get_risk_by_site(request.site_id)
                baseline_record = rec.model_dump()
            except HTTPException:
                pass

        if not baseline_record and (request.latitude and request.longitude):
            baseline_record = {
                "site_id": "CUSTOM_SITE",
                "site_name": "Custom Location",
                "state": "NER",
                "latitude": request.latitude,
                "longitude": request.longitude,
            }

        if not baseline_record and self._risk_df is not None and not self._risk_df.empty:
            baseline_record = self._risk_df.iloc[0].to_dict()

        # Provide terrain fallbacks if elevation_m or slope_deg are None/missing
        if baseline_record.get("elevation_m") is None:
            baseline_record["elevation_m"] = 1250.0
        if baseline_record.get("slope_deg") is None:
            baseline_record["slope_deg"] = 28.5
        if baseline_record.get("historical_count_5km") is None:
            baseline_record["historical_count_5km"] = 4.0
        if baseline_record.get("historical_count_10km") is None:
            baseline_record["historical_count_10km"] = 12.0

        baseline_risk_score = _sanitize_float(baseline_record.get("current_risk_score"))
        baseline_risk_level = _clean_str(baseline_record.get("current_risk_level"), "MODERATE")

        # Execute Phase 7 demo simulation function
        sim_output = simulate_dynamic_risk_scenario(
            baseline_location_record=baseline_record,
            simulated_rainfall_1d=request.simulated_rainfall_1d,
            simulated_rainfall_3d=request.simulated_rainfall_3d,
            simulated_rainfall_7d=request.simulated_rainfall_7d,
            simulated_soil_moisture=sm_val,
            scenario_name=request.scenario_name,
        )

        # Convert output to response schema
        sim_output["site_id"] = _clean_str(baseline_record.get("site_id", "DEMO_SITE"))
        sim_output["site_name"] = _clean_str(baseline_record.get("site_name", "Demo Location"))
        sim_output["state"] = _clean_str(baseline_record.get("state", "NER"))
        sim_output["district"] = _clean_str(baseline_record.get("district", "NER"))
        sim_output["scenario_name"] = request.scenario_name
        sim_output["baseline_current_risk_score"] = baseline_risk_score
        sim_output["baseline_current_risk_level"] = baseline_risk_level
        sim_output["simulated_current_risk_score"] = _sanitize_float(sim_output.get("current_risk_score")) or 0.0
        sim_output["simulated_current_risk_level"] = _clean_str(sim_output.get("current_risk_level"), "HIGH")
        sim_output["freshness_status"] = "SIMULATED_SCENARIO"
        sim_output["is_live"] = False

        return DemoSimulationResponse(**sim_output)
