"""Demo Mode Simulation Layer for ResQtech.

Provides a controlled simulation layer for judge/demo presentations, enabling what-if scenario
testing (e.g. simulating a severe monsoon rainfall spike to demonstrate MODERATE -> HIGH risk transition).

CRITICAL SCIENTIFIC SAFETY RULES:
1. Simulation MUST be explicitly tagged with simulation_mode = True and data_source = "SIMULATED_DEMO".
2. Simulated observations MUST NEVER overwrite or mutate real historical satellite records in data/processed.
"""

import logging
from typing import Dict, Any, Optional
import numpy as np

from src.risk.trigger_engine import DynamicTriggerEngine
from src.risk.susceptibility import StaticSusceptibilityEngine
from src.risk.risk_fusion import RiskFusionEngine, CALIBRATION_DISCLAIMER

logger = logging.getLogger(__name__)


def simulate_dynamic_risk_scenario(
    baseline_location_record: Dict[str, Any],
    simulated_rainfall_1d: float,
    simulated_rainfall_3d: float,
    simulated_rainfall_7d: float,
    simulated_soil_moisture: float,
    scenario_name: str = "Monsoon Heavy Rainfall Spike",
) -> Dict[str, Any]:
    """Execute what-if simulation for a real pilot location baseline.

    Args:
        baseline_location_record: Real location dictionary containing latitude, longitude, and static terrain features.
        simulated_rainfall_1d: Override 1-day rainfall in mm/day.
        simulated_rainfall_3d: Override 3-day rainfall accumulation in mm.
        simulated_rainfall_7d: Override 7-day rainfall accumulation in mm.
        simulated_soil_moisture: Override soil moisture in cm^3/cm^3 (0.0 - 0.50).
        scenario_name: Descriptive label for the demo scenario.

    Returns:
        Dict containing full fused current risk marked with simulation_mode = True and data_source = "SIMULATED_DEMO".
    """
    trigger_engine = DynamicTriggerEngine()
    susceptibility_engine = StaticSusceptibilityEngine()
    fusion_engine = RiskFusionEngine()

    lat = float(baseline_location_record.get("latitude", 26.0))
    lon = float(baseline_location_record.get("longitude", 91.0))

    def _to_float(val):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return np.nan
        try:
            return float(val)
        except (ValueError, TypeError):
            return np.nan

    # Evaluate static susceptibility for baseline terrain
    static_res = susceptibility_engine.evaluate_static_susceptibility(
        latitude=lat,
        longitude=lon,
        elevation_m=_to_float(baseline_location_record.get("elevation_m")),
        slope_deg=_to_float(baseline_location_record.get("slope_deg")),
        historical_count_5km=_to_float(baseline_location_record.get("historical_count_5km")),
        historical_count_10km=_to_float(baseline_location_record.get("historical_count_10km")),
        feature_dict=baseline_location_record,
    )

    # Recompute dynamic trigger under simulated environmental conditions
    sim_date = baseline_location_record.get("observation_date", "2025-07-04")
    dynamic_res = trigger_engine.calculate_trigger(
        rainfall_1d=simulated_rainfall_1d,
        rainfall_3d=simulated_rainfall_3d,
        rainfall_7d=simulated_rainfall_7d,
        soil_moisture=simulated_soil_moisture,
        rainfall_data_status="VALID",
        soil_moisture_data_status="VALID",
        observation_date=f"{sim_date}_SIMULATED",
        source_provenance="SIMULATED_DEMO_ENGINE",
    )

    # Previous baseline score for trend comparison if present
    prev_score = baseline_location_record.get("current_risk_score", None)
    prev_level = baseline_location_record.get("current_risk_level", None)

    # Fuse layers
    fused = fusion_engine.fuse(
        static_result=static_res,
        dynamic_result=dynamic_res,
        previous_risk_score=prev_score,
        previous_risk_level=prev_level,
    )

    # Attach explicit simulation flags & provenance
    fused["simulation_mode"] = True
    fused["data_source"] = "SIMULATED_DEMO"
    fused["scenario_name"] = scenario_name
    fused["baseline_location_id"] = baseline_location_record.get("site_id", baseline_location_record.get("location_id", "PILOT_LOC"))
    fused["site_name"] = baseline_location_record.get("site_name", "Demo Site")
    fused["state"] = baseline_location_record.get("state", "NER")

    # Update explanation narrative to note simulation
    orig_narrative = fused.get("risk_explanation", "")
    fused["risk_explanation"] = f"[DEMO SIMULATION: {scenario_name}] {orig_narrative}"

    return fused
