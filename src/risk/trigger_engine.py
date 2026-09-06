"""Dynamic Trigger Engine for ResQtech.

Calculates Layer 2 deterministic environmental trigger pressure score [0–100]
based on NASA IMERG antecedent rainfall accumulation (1-day, 3-day, 7-day) and
NASA SMAP volumetric soil moisture.

IMPORTANT SCIENTIFIC DISCLAIMER:
This module represents an OPERATIONAL DYNAMIC TRIGGER ENGINE using prototype rules
and thresholds. It is NOT a calibrated landslide probability. Thresholds and weights
must be scientifically calibrated for specific regional catchments.
"""

import logging
from typing import Dict, List, Optional, Union
import numpy as np

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# Calibration disclaimer
CALIBRATION_DISCLAIMER = (
    "PROTOTYPE OPERATIONAL TRIGGER PARAMETERS — REQUIRES REGIONAL SCIENTIFIC CALIBRATION"
)


class DynamicTriggerEngine:
    """Deterministic prototype engine for computing dynamic environmental trigger scores."""

    def __init__(self):
        """Initialize trigger engine with settings."""
        self.settings = get_settings()

        # Prototype Thresholds
        self.high_threshold = self.settings.TRIGGER_HIGH_THRESHOLD  # e.g., 70.0
        self.mod_threshold = self.settings.TRIGGER_MOD_THRESHOLD    # e.g., 40.0

        # Prototype Weights (Sum to 1.0)
        self.weight_1d = 0.30  # Recent daily intensity
        self.weight_3d = 0.30  # 3-day accumulation
        self.weight_7d = 0.20  # 7-day antecedent precipitation
        self.weight_sm = 0.20  # Volumetric soil moisture state

        # Reference scaling baselines for 100% component pressure
        self.ref_r1d_mm = 100.0   # 100 mm/day heavy rainfall
        self.ref_r3d_mm = 150.0   # 150 mm in 3 days
        self.ref_r7d_mm = 250.0   # 250 mm in 7 days
        self.ref_sm_sat = 0.45    # 0.45 cm^3/cm^3 near saturated soil capacity

    def calculate_trigger(
        self,
        rainfall_1d: float,
        rainfall_3d: float,
        rainfall_7d: float,
        soil_moisture: float,
        rainfall_data_status: str = "VALID",
        soil_moisture_data_status: str = "VALID",
        observation_date: Optional[str] = None,
        source_provenance: Optional[str] = "NASA IMERG + NASA SMAP L3",
    ) -> Dict[str, Union[float, str, List[str], Dict[str, str]]]:
        """Calculate dynamic trigger score and assigned trigger level.

        Args:
            rainfall_1d: 1-day rainfall accumulation in mm/day.
            rainfall_3d: 3-day accumulated rainfall in mm.
            rainfall_7d: 7-day accumulated rainfall in mm.
            soil_moisture: Volumetric soil moisture in cm^3/cm^3.
            rainfall_data_status: Status string for rainfall data.
            soil_moisture_data_status: Status string for soil moisture data.
            observation_date: ISO date string (YYYY-MM-DD).
            source_provenance: Data source metadata string.

        Returns:
            Dict containing dynamic_trigger_score, dynamic_trigger_level,
            dynamic_major_factors, dynamic_data_status, data_completeness,
            source_provenance, and disclaimer.
        """
        # Check completeness and validity
        r_valid = not np.isnan(rainfall_1d) and rainfall_data_status in ["VALID", "COMPLETE"]
        sm_valid = not np.isnan(soil_moisture) and soil_moisture_data_status in ["VALID", "RECOMMENDED", "HIGH", "WARNING"]

        data_completeness = {
            "rainfall_status": rainfall_data_status,
            "soil_moisture_status": soil_moisture_data_status,
            "rainfall_1d_available": not np.isnan(rainfall_1d),
            "rainfall_3d_available": not np.isnan(rainfall_3d),
            "rainfall_7d_available": not np.isnan(rainfall_7d),
            "soil_moisture_available": not np.isnan(soil_moisture),
        }

        # Dynamic data status classification
        if not r_valid or np.isnan(rainfall_1d):
            dyn_data_status = "INSUFFICIENT_DATA"
        elif not sm_valid or np.isnan(soil_moisture):
            dyn_data_status = "PARTIAL_RAINFALL_ONLY"
        else:
            dyn_data_status = "VALID"

        # Handle missing or insufficient data gracefully
        if not r_valid or np.isnan(rainfall_1d):
            return {
                "observation_date": observation_date or "",
                "rainfall_1d": float(rainfall_1d) if not np.isnan(rainfall_1d) else np.nan,
                "rainfall_3d": float(rainfall_3d) if not np.isnan(rainfall_3d) else np.nan,
                "rainfall_7d": float(rainfall_7d) if not np.isnan(rainfall_7d) else np.nan,
                "soil_moisture": float(soil_moisture) if not np.isnan(soil_moisture) else np.nan,
                "dynamic_trigger_score": np.nan,
                "dynamic_trigger_level": "INSUFFICIENT_DATA",
                "dynamic_data_status": "INSUFFICIENT_DATA",
                "major_trigger_factors": ["Missing or insufficient rainfall history"],
                "dynamic_major_factors": ["Missing or insufficient rainfall history"],
                "data_completeness": data_completeness,
                "source_provenance": source_provenance,
                "calibration_disclaimer": CALIBRATION_DISCLAIMER,
            }

        # Calculate sub-scores (0.0 to 100.0)
        s_r1d = min(100.0, max(0.0, (rainfall_1d / self.ref_r1d_mm) * 100.0))

        # If 3d or 7d rainfall is missing due to gaps, fallback gracefully to available history
        s_r3d = min(100.0, max(0.0, (rainfall_3d / self.ref_r3d_mm) * 100.0)) if not np.isnan(rainfall_3d) else s_r1d
        s_r7d = min(100.0, max(0.0, (rainfall_7d / self.ref_r7d_mm) * 100.0)) if not np.isnan(rainfall_7d) else s_r3d

        # Soil moisture sub-score
        if sm_valid and not np.isnan(soil_moisture):
            s_sm = min(100.0, max(0.0, (soil_moisture / self.ref_sm_sat) * 100.0))
        else:
            # If soil moisture is invalid/missing, redistribute weight to rainfall components
            s_sm = 0.0

        # Compute weighted trigger score
        if sm_valid and not np.isnan(soil_moisture):
            score = (
                self.weight_1d * s_r1d +
                self.weight_3d * s_r3d +
                self.weight_7d * s_r7d +
                self.weight_sm * s_sm
            )
        else:
            # Re-normalize rainfall weights to 1.0 when SM is unavailable
            w_sum = self.weight_1d + self.weight_3d + self.weight_7d
            score = (
                (self.weight_1d / w_sum) * s_r1d +
                (self.weight_3d / w_sum) * s_r3d +
                (self.weight_7d / w_sum) * s_r7d
            )

        score = round(float(min(100.0, max(0.0, score))), 2)

        # Assign trigger level
        if score >= self.high_threshold:
            level = "HIGH"
        elif score >= self.mod_threshold:
            level = "MODERATE"
        else:
            level = "LOW"

        # Identify major contributing trigger factors
        factors = []
        if rainfall_1d >= 50.0:
            factors.append(f"Heavy 1-day rainfall accumulation ({rainfall_1d:.1f} mm/day)")
        if not np.isnan(rainfall_3d) and rainfall_3d >= 100.0:
            factors.append(f"High 3-day antecedent precipitation ({rainfall_3d:.1f} mm)")
        if not np.isnan(rainfall_7d) and rainfall_7d >= 175.0:
            factors.append(f"Sustained 7-day antecedent precipitation ({rainfall_7d:.1f} mm)")
        if sm_valid and not np.isnan(soil_moisture) and soil_moisture >= 0.30:
            factors.append(f"High volumetric soil moisture saturation ({soil_moisture:.3f} cm³/cm³)")

        if not factors:
            factors.append("Low overall dynamic environmental triggering pressure")

        return {
            "observation_date": observation_date or "",
            "rainfall_1d": float(rainfall_1d) if not np.isnan(rainfall_1d) else np.nan,
            "rainfall_3d": float(rainfall_3d) if not np.isnan(rainfall_3d) else np.nan,
            "rainfall_7d": float(rainfall_7d) if not np.isnan(rainfall_7d) else np.nan,
            "soil_moisture": float(soil_moisture) if not np.isnan(soil_moisture) else np.nan,
            "dynamic_trigger_score": score,
            "dynamic_trigger_level": level,
            "dynamic_data_status": dyn_data_status,
            "major_trigger_factors": factors,
            "dynamic_major_factors": factors,
            "data_completeness": data_completeness,
            "source_provenance": source_provenance,
            "calibration_disclaimer": CALIBRATION_DISCLAIMER,
        }


def calculate_dynamic_trigger_score(
    rainfall_1d_mm: float,
    rainfall_3d_mm: float,
    rainfall_7d_mm: float,
    soil_moisture_pct: float,
) -> float:
    """Backwards-compatible convenience function returning trigger score (0-100).

    Args:
        rainfall_1d_mm: 1-day rainfall accumulation in mm.
        rainfall_3d_mm: 3-day accumulated precipitation in mm.
        rainfall_7d_mm: 7-day accumulated precipitation in mm.
        soil_moisture_pct: Soil moisture percentage or volumetric fraction.

    Returns:
        Dynamic trigger score [0.0, 100.0].
    """
    engine = DynamicTriggerEngine()
    # Normalize percentage if passed as 0-100 scale
    sm_val = soil_moisture_pct / 100.0 if soil_moisture_pct > 1.0 else soil_moisture_pct
    res = engine.calculate_trigger(rainfall_1d_mm, rainfall_3d_mm, rainfall_7d_mm, sm_val)
    score = res["dynamic_trigger_score"]
    return 0.0 if np.isnan(score) else float(score)
