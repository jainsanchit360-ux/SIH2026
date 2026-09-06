"""Layer 1: Static Landslide Susceptibility Calculation Interface.

Evaluates terrain susceptibility score [0–100] based on Phase 5B trained Random Forest model
and static spatial predictors (elevation, slope, historical landslide density).

IMPORTANT SCIENTIFIC TERMINOLOGY DISCLAIMER:
Static susceptibility represents terrain and historical spatial predisposition to landslides.
The score is a prototype operational screening score [0–100] and NOT a calibrated probability.
Outputs must be explicitly labelled:
"PROTOTYPE OPERATIONAL PARAMETERS — REQUIRES REGIONAL CALIBRATION"
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import joblib
import numpy as np
import pandas as pd

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

CALIBRATION_DISCLAIMER = (
    "PROTOTYPE OPERATIONAL PARAMETERS — REQUIRES REGIONAL CALIBRATION"
)


class StaticSusceptibilityEngine:
    """Reusable engine for evaluating static landslide susceptibility scores and drivers."""

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        metadata_path: Optional[Union[str, Path]] = None,
    ):
        """Initialize static susceptibility engine with trained model and metadata."""
        self.settings = get_settings()

        # Resolve model path (prefer Phase 5B model)
        if model_path is None:
            p5b_path = self.settings.MODELS_TRAINED_DIR / "static_susceptibility_model_phase5b.joblib"
            p5a_path = self.settings.MODELS_TRAINED_DIR / "static_susceptibility_model.joblib"
            model_path = p5b_path if p5b_path.exists() else p5a_path

        # Resolve metadata path
        if metadata_path is None:
            p5b_meta = self.settings.MODELS_METADATA_DIR / "static_susceptibility_model_metadata_phase5b.json"
            p5a_meta = self.settings.MODELS_METADATA_DIR / "static_susceptibility_model_metadata.json"
            metadata_path = p5b_meta if p5b_meta.exists() else p5a_meta

        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)

        self.model = None
        self.metadata = {}
        self.model_version = "1.1.0-phase5b"
        self.feature_names = ["elevation_m", "slope_deg", "historical_count_5km", "historical_count_10km"]

        self._load_artifacts()

    def _load_artifacts(self):
        """Load joblib model artifact and JSON metadata."""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                self.model_version = self.metadata.get("model_version", self.model_version)
                if "primary_features" in self.metadata:
                    self.feature_names = self.metadata["primary_features"]
            except Exception as e:
                logger.warning(f"Failed to load model metadata from {self.metadata_path}: {e}")

        if self.model_path.exists():
            try:
                self.model = joblib.load(self.model_path)
                logger.info(f"Loaded static susceptibility model from {self.model_path}")
            except Exception as e:
                logger.warning(f"Failed to load model artifact from {self.model_path}: {e}")
        else:
            logger.warning(f"Model artifact not found at {self.model_path}")

    def classify_susceptibility_level(self, score: float) -> str:
        """Classify static susceptibility score (0-100) into prototype level.

        Thresholds:
        - 0.0 - 39.9: LOW
        - 40.0 - 69.9: MODERATE
        - 70.0 - 100.0: HIGH
        """
        if np.isnan(score):
            return "INSUFFICIENT_DATA"
        elif score >= self.settings.SUSCEPTIBILITY_HIGH_THRESHOLD * 100.0:
            return "HIGH"
        elif score >= self.settings.SUSCEPTIBILITY_MOD_THRESHOLD * 100.0:
            return "MODERATE"
        else:
            return "LOW"

    def derive_static_major_factors(
        self,
        elevation_m: float,
        slope_deg: float,
        historical_count_5km: float,
        historical_count_10km: float,
    ) -> List[str]:
        """Generate human-readable static terrain and spatial drivers."""
        factors = []
        if not np.isnan(slope_deg):
            if slope_deg >= 25.0:
                factors.append(f"Steep terrain slope ({slope_deg:.1f}°)")
            elif slope_deg >= 15.0:
                factors.append(f"Moderate terrain slope ({slope_deg:.1f}°)")

        if not np.isnan(historical_count_5km) and historical_count_5km >= 5:
            factors.append(f"Dense historical landslide concentration within 5km radius ({int(historical_count_5km)} records)")
        elif not np.isnan(historical_count_5km) and historical_count_5km >= 1:
            factors.append(f"Known historical landslide presence within 5km radius ({int(historical_count_5km)} record)")

        if not np.isnan(historical_count_10km) and historical_count_10km >= 10:
            factors.append(f"Elevated regional landslide count within 10km radius ({int(historical_count_10km)} records)")

        if not np.isnan(elevation_m) and elevation_m >= 1000.0:
            factors.append(f"High terrain elevation ({elevation_m:.0f} m)")

        if not factors:
            factors.append("Low terrain slope and sparse historical landslide density")

        return factors

    def evaluate_static_susceptibility(
        self,
        latitude: float,
        longitude: float,
        elevation_m: float = np.nan,
        slope_deg: float = np.nan,
        historical_count_5km: float = np.nan,
        historical_count_10km: float = np.nan,
        feature_dict: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluate Layer 1 static susceptibility result for a single point.

        Args:
            latitude: Geographic latitude.
            longitude: Geographic longitude.
            elevation_m: Elevation in meters.
            slope_deg: Slope in degrees.
            historical_count_5km: Historical GSI landslide count in 5km radius.
            historical_count_10km: Historical GSI landslide count in 10km radius.
            feature_dict: Optional feature dictionary overriding arguments.

        Returns:
            Dict containing:
            - latitude
            - longitude
            - static_susceptibility_score (0.0 to 100.0)
            - static_susceptibility_level ("LOW", "MODERATE", "HIGH", "INSUFFICIENT_DATA")
            - static_model_version
            - static_model_features
            - static_major_factors
            - static_data_status
            - calibration_disclaimer
        """
        # Validate spatial bounding box
        ner_min_lon, ner_min_lat, ner_max_lon, ner_max_lat = self.settings.ner_bbox
        is_ner = (ner_min_lat <= latitude <= ner_max_lat) and (ner_min_lon <= longitude <= ner_max_lon)

        if not is_ner:
            return {
                "latitude": float(latitude),
                "longitude": float(longitude),
                "static_susceptibility_score": np.nan,
                "static_susceptibility_level": "INSUFFICIENT_DATA",
                "static_model_version": self.model_version,
                "static_model_features": {},
                "static_major_factors": ["Location outside North-Eastern Region (NER) bounding box"],
                "static_data_status": "OUT_OF_BOUNDS",
                "calibration_disclaimer": CALIBRATION_DISCLAIMER,
            }

        # Override with feature dict if provided
        if feature_dict:
            elevation_m = feature_dict.get("elevation_m", elevation_m)
            slope_deg = feature_dict.get("slope_deg", slope_deg)
            historical_count_5km = feature_dict.get("historical_count_5km", historical_count_5km)
            historical_count_10km = feature_dict.get("historical_count_10km", historical_count_10km)

        # Check completeness
        missing_inputs = []
        if np.isnan(elevation_m):
            missing_inputs.append("elevation_m")
        if np.isnan(slope_deg):
            missing_inputs.append("slope_deg")
        if np.isnan(historical_count_5km):
            missing_inputs.append("historical_count_5km")
        if np.isnan(historical_count_10km):
            missing_inputs.append("historical_count_10km")

        features_input = {
            "elevation_m": float(elevation_m) if not np.isnan(elevation_m) else np.nan,
            "slope_deg": float(slope_deg) if not np.isnan(slope_deg) else np.nan,
            "historical_count_5km": float(historical_count_5km) if not np.isnan(historical_count_5km) else np.nan,
            "historical_count_10km": float(historical_count_10km) if not np.isnan(historical_count_10km) else np.nan,
        }

        if missing_inputs or self.model is None:
            status = "MISSING_DATA" if missing_inputs else "MODEL_UNAVAILABLE"
            return {
                "latitude": float(latitude),
                "longitude": float(longitude),
                "static_susceptibility_score": np.nan,
                "static_susceptibility_level": "INSUFFICIENT_DATA",
                "static_model_version": self.model_version,
                "static_model_features": features_input,
                "static_major_factors": [f"Missing required static predictors: {', '.join(missing_inputs)}"],
                "static_data_status": status,
                "calibration_disclaimer": CALIBRATION_DISCLAIMER,
            }

        # Execute model inference
        X_df = pd.DataFrame([features_input])[self.feature_names]
        prob = float(self.model.predict_proba(X_df)[0, 1])
        score = round(float(prob * 100.0), 2)
        score_clipped = float(min(100.0, max(0.0, score)))

        level = self.classify_susceptibility_level(score_clipped)
        factors = self.derive_static_major_factors(
            elevation_m=elevation_m,
            slope_deg=slope_deg,
            historical_count_5km=historical_count_5km,
            historical_count_10km=historical_count_10km,
        )

        return {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "static_susceptibility_score": score_clipped,
            "static_susceptibility_level": level,
            "static_model_version": self.model_version,
            "static_model_features": features_input,
            "static_major_factors": factors,
            "static_data_status": "VALID",
            "calibration_disclaimer": CALIBRATION_DISCLAIMER,
        }


def calculate_static_susceptibility_score(
    elevation_m: float,
    slope_deg: float,
    landslide_density_5km: float = 0.0,
    land_cover_class: Optional[int] = None,
    latitude: float = 26.0,
    longitude: float = 91.0,
    historical_count_10km: Optional[float] = None,
) -> float:
    """Convenience function calculating static susceptibility score (0-100).

    Args:
        elevation_m: Elevation in meters.
        slope_deg: Terrain slope angle in degrees.
        landslide_density_5km: Historical landslide count within 5km radius.
        land_cover_class: Optional ESA land cover class code.
        latitude: Latitude.
        longitude: Longitude.
        historical_count_10km: Historical count within 10km radius.

    Returns:
        Static susceptibility score [0.0 - 100.0].
    """
    engine = StaticSusceptibilityEngine()
    h10 = historical_count_10km if historical_count_10km is not None else landslide_density_5km * 2.0
    res = engine.evaluate_static_susceptibility(
        latitude=latitude,
        longitude=longitude,
        elevation_m=elevation_m,
        slope_deg=slope_deg,
        historical_count_5km=landslide_density_5km,
        historical_count_10km=h10,
    )
    score = res["static_susceptibility_score"]
    return 0.0 if np.isnan(score) else float(score)
