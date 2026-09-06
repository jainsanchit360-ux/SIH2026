"""Two-Layer Risk Fusion Engine for ResQtech.

Combines Layer 1 Static Susceptibility [0–100] and Layer 2 Dynamic Environmental Trigger Pressure [0–100]
into Current Landslide Risk [0–100], categorized as LOW, MODERATE, HIGH, or INSUFFICIENT_DATA.

CRITICAL SCIENTIFIC DISCLAIMER:
Current landslide risk is a prototype operational fusion of static susceptibility and dynamic trigger pressure.
It is NOT a calibrated probability of landslide occurrence, nor does it predict exact failure time.
All outputs include the explicit label:
"PROTOTYPE OPERATIONAL PARAMETERS — REQUIRES REGIONAL CALIBRATION"
"""

import logging
from typing import Dict, List, Optional, Union, Any
import numpy as np

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

CALIBRATION_DISCLAIMER = (
    "PROTOTYPE OPERATIONAL PARAMETERS — REQUIRES REGIONAL CALIBRATION"
)


class RiskFusionEngine:
    """Engine for fusing static susceptibility and dynamic trigger scores into operational risk."""

    def __init__(self):
        """Initialize fusion engine with settings."""
        self.settings = get_settings()
        self.static_weight = self.settings.FUSION_STATIC_WEIGHT    # 0.50
        self.dynamic_weight = self.settings.FUSION_DYNAMIC_WEIGHT  # 0.50
        self.high_threshold = self.settings.RISK_HIGH_THRESHOLD    # 70.0
        self.mod_threshold = self.settings.RISK_MOD_THRESHOLD      # 40.0
        self.stable_tolerance = self.settings.STABLE_TREND_TOLERANCE  # 2.0

    def classify_risk_level(self, score: float) -> str:
        """Classify current risk score (0-100) into risk level.

        Thresholds:
        - 0.0 - 39.9: LOW
        - 40.0 - 69.9: MODERATE
        - 70.0 - 100.0: HIGH
        """
        if np.isnan(score):
            return "INSUFFICIENT_DATA"
        elif score >= self.high_threshold:
            return "HIGH"
        elif score >= self.mod_threshold:
            return "MODERATE"
        else:
            return "LOW"

    def compute_trend(
        self,
        current_score: float,
        previous_score: Optional[float] = None,
    ) -> Dict[str, Union[float, str]]:
        """Compute numerical risk change and risk trend category.

        Trends:
        - RISING: change > +2.0
        - FALLING: change < -2.0
        - STABLE: |change| <= 2.0
        - UNKNOWN: previous_score is missing or NaN
        """
        if previous_score is None or np.isnan(previous_score) or np.isnan(current_score):
            return {
                "previous_risk_score": np.nan,
                "risk_score_change": np.nan,
                "risk_trend": "UNKNOWN",
            }

        change = round(float(current_score - previous_score), 2)
        if change > self.stable_tolerance:
            trend = "RISING"
        elif change < -self.stable_tolerance:
            trend = "FALLING"
        else:
            trend = "STABLE"

        return {
            "previous_risk_score": round(float(previous_score), 2),
            "risk_score_change": change,
            "risk_trend": trend,
        }

    def generate_explainability(
        self,
        current_risk_score: float,
        current_risk_level: str,
        static_score: float,
        dynamic_score: float,
        static_factors: List[str],
        dynamic_factors: List[str],
        previous_risk_score: Optional[float] = None,
        previous_risk_level: Optional[str] = None,
    ) -> Dict[str, Union[List[str], str]]:
        """Generate human-readable explanations and what_changed narrative."""
        if current_risk_level == "INSUFFICIENT_DATA":
            return {
                "major_risk_factors": ["Insufficient data available to compute landslide risk"],
                "static_contributors": static_factors if static_factors else [],
                "dynamic_contributors": dynamic_factors if dynamic_factors else [],
                "risk_explanation": "Current risk cannot be determined due to missing static susceptibility or environmental trigger data.",
                "what_changed": "Trend unavailable due to missing observation data.",
            }

        # Deduplicate and combine contributors
        all_factors = []
        for f in static_factors + dynamic_factors:
            if f and f not in all_factors and "Low overall" not in f and "Low terrain" not in f:
                all_factors.append(f)

        if not all_factors:
            all_factors = ["Baseline terrain predisposition and baseline weather conditions"]

        # Formulate risk narrative
        narrative = (
            f"Location classified at {current_risk_level} Current Risk (score {current_risk_score:.1f}/100) based on "
            f"Static Susceptibility ({static_score:.1f}/100) and Dynamic Environmental Trigger ({dynamic_score:.1f}/100). "
            f"Primary factors: {'; '.join(all_factors)}."
        )

        # Formulate what_changed narrative if previous data exists
        if previous_risk_score is not None and not np.isnan(previous_risk_score):
            score_change = current_risk_score - previous_risk_score
            prev_lvl = previous_risk_level or self.classify_risk_level(previous_risk_score)
            if abs(score_change) <= self.stable_tolerance:
                what_changed = f"Risk remained STABLE at {current_risk_level} (score change {score_change:+.1f})."
            elif score_change > 0:
                what_changed = (
                    f"Risk increased from {prev_lvl} to {current_risk_level} (score change +{score_change:.1f}) "
                    f"primarily due to increased dynamic triggering pressure."
                )
            else:
                what_changed = (
                    f"Risk decreased from {prev_lvl} to {current_risk_level} (score change {score_change:.1f}) "
                    f"as dynamic environmental triggering pressure attenuated."
                )
        else:
            what_changed = "No previous observation available for trend comparison."

        return {
            "major_risk_factors": all_factors,
            "static_contributors": static_factors,
            "dynamic_contributors": dynamic_factors,
            "risk_explanation": narrative,
            "what_changed": what_changed,
        }

    def fuse(
        self,
        static_result: Dict[str, Any],
        dynamic_result: Dict[str, Any],
        previous_risk_score: Optional[float] = None,
        previous_risk_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fuse static susceptibility result and dynamic trigger result into Current Risk.

        Args:
            static_result: Result dictionary from StaticSusceptibilityEngine.
            dynamic_result: Result dictionary from DynamicTriggerEngine.
            previous_risk_score: Optional risk score from previous observation.
            previous_risk_level: Optional risk level from previous observation.

        Returns:
            Dict containing full fused current risk schema.
        """
        static_score = static_result.get("static_susceptibility_score", np.nan)
        static_status = static_result.get("static_data_status", "UNKNOWN")
        static_factors = static_result.get("static_major_factors", [])

        dynamic_score = dynamic_result.get("dynamic_trigger_score", np.nan)
        dynamic_status = dynamic_result.get("dynamic_data_status", "UNKNOWN")
        dynamic_factors = dynamic_result.get("dynamic_major_factors", dynamic_result.get("major_trigger_factors", []))

        missing_inputs = []
        if np.isnan(static_score) or static_status not in ["VALID"]:
            missing_inputs.append("static_susceptibility")

        if np.isnan(dynamic_score) or dynamic_status == "INSUFFICIENT_DATA":
            missing_inputs.append("dynamic_trigger_rainfall")

        if dynamic_status == "PARTIAL_RAINFALL_ONLY":
            missing_inputs.append("soil_moisture")

        # Failure policy check: static missing or dynamic history missing yields INSUFFICIENT_DATA
        if np.isnan(static_score) or np.isnan(dynamic_score) or "static_susceptibility" in missing_inputs or "dynamic_trigger_rainfall" in missing_inputs:
            current_risk_score = np.nan
            current_risk_level = "INSUFFICIENT_DATA"
            confidence_status = "INSUFFICIENT_DATA"
        else:
            # Deterministic weighted fusion
            raw_score = (self.static_weight * static_score) + (self.dynamic_weight * dynamic_score)
            current_risk_score = round(float(min(100.0, max(0.0, raw_score))), 2)
            current_risk_level = self.classify_risk_level(current_risk_score)

            if "soil_moisture" in missing_inputs:
                confidence_status = "DEGRADED_CONFIDENCE_RAINFALL_ONLY"
            else:
                confidence_status = "HIGH_CONFIDENCE_COMPLETE"

        # Data completeness tracking
        data_completeness = {
            "static_available": not np.isnan(static_score),
            "rainfall_available": not np.isnan(dynamic_result.get("rainfall_1d", np.nan)),
            "soil_moisture_available": not np.isnan(dynamic_result.get("soil_moisture", np.nan)),
            "confidence_status": confidence_status,
            "missing_inputs": missing_inputs,
            "staleness_status": "FRESH",
        }

        # Trend computation
        trend_info = self.compute_trend(current_risk_score, previous_risk_score)

        # Explainability generation
        explain_info = self.generate_explainability(
            current_risk_score=current_risk_score,
            current_risk_level=current_risk_level,
            static_score=static_score if not np.isnan(static_score) else 0.0,
            dynamic_score=dynamic_score if not np.isnan(dynamic_score) else 0.0,
            static_factors=static_factors,
            dynamic_factors=dynamic_factors,
            previous_risk_score=previous_risk_score,
            previous_risk_level=previous_risk_level,
        )

        return {
            "latitude": static_result.get("latitude", np.nan),
            "longitude": static_result.get("longitude", np.nan),
            "observation_date": dynamic_result.get("observation_date", ""),
            
            # Static susceptibility layer
            "static_susceptibility_score": static_score,
            "static_susceptibility_level": static_result.get("static_susceptibility_level", "INSUFFICIENT_DATA"),
            "static_model_version": static_result.get("static_model_version", "1.1.0-phase5b"),

            # Environmental trigger layer
            "rainfall_1d": dynamic_result.get("rainfall_1d", np.nan),
            "rainfall_3d": dynamic_result.get("rainfall_3d", np.nan),
            "rainfall_7d": dynamic_result.get("rainfall_7d", np.nan),
            "soil_moisture": dynamic_result.get("soil_moisture", np.nan),
            "dynamic_trigger_score": dynamic_score,
            "dynamic_trigger_level": dynamic_result.get("dynamic_trigger_level", "INSUFFICIENT_DATA"),

            # Fused current risk
            "current_risk_score": current_risk_score,
            "current_risk_level": current_risk_level,
            
            # Trend support
            "previous_risk_score": trend_info["previous_risk_score"],
            "risk_score_change": trend_info["risk_score_change"],
            "risk_trend": trend_info["risk_trend"],

            # Risk explainability
            "major_risk_factors": explain_info["major_risk_factors"],
            "static_contributors": explain_info["static_contributors"],
            "dynamic_contributors": explain_info["dynamic_contributors"],
            "risk_explanation": explain_info["risk_explanation"],
            "what_changed": explain_info["what_changed"],

            # Provenance and metadata
            "data_completeness": data_completeness,
            "source_provenance": dynamic_result.get("source_provenance", "NASA IMERG + NASA SMAP L3"),
            "fusion_weights": {
                "static_weight": self.static_weight,
                "dynamic_weight": self.dynamic_weight,
            },
            "calibration_disclaimer": CALIBRATION_DISCLAIMER,
        }


def fuse_risk_layers(
    susceptibility_score: float,
    trigger_score: float,
    previous_risk_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Convenience function fusing static susceptibility score and dynamic trigger score.

    Args:
        susceptibility_score: Static susceptibility score [0.0 - 100.0].
        trigger_score: Dynamic environmental trigger score [0.0 - 100.0].
        previous_risk_score: Optional previous risk score for trend calculation.

    Returns:
        Dict containing combined_risk_score, risk_level, trend, and calibration notice.
    """
    engine = RiskFusionEngine()
    static_res = {
        "latitude": 26.0,
        "longitude": 91.0,
        "static_susceptibility_score": susceptibility_score,
        "static_susceptibility_level": engine.classify_risk_level(susceptibility_score),
        "static_data_status": "VALID" if not np.isnan(susceptibility_score) else "MISSING_DATA",
        "static_major_factors": ["Static terrain susceptibility"],
    }

    dynamic_res = {
        "observation_date": "",
        "rainfall_1d": np.nan,
        "rainfall_3d": np.nan,
        "rainfall_7d": np.nan,
        "soil_moisture": np.nan,
        "dynamic_trigger_score": trigger_score,
        "dynamic_trigger_level": engine.classify_risk_level(trigger_score),
        "dynamic_data_status": "VALID" if not np.isnan(trigger_score) else "INSUFFICIENT_DATA",
        "dynamic_major_factors": ["Dynamic environmental trigger pressure"],
        "source_provenance": "NASA IMERG + SMAP",
    }

    fused = engine.fuse(static_res, dynamic_res, previous_risk_score=previous_risk_score)
    return {
        "susceptibility_score": fused["static_susceptibility_score"],
        "trigger_score": fused["dynamic_trigger_score"],
        "combined_risk_score": fused["current_risk_score"],
        "current_risk_score": fused["current_risk_score"],
        "risk_level": fused["current_risk_level"],
        "current_risk_level": fused["current_risk_level"],
        "risk_trend": fused["risk_trend"],
        "risk_explanation": fused["risk_explanation"],
        "calibration_notice": fused["calibration_disclaimer"],
        "calibration_disclaimer": fused["calibration_disclaimer"],
    }
