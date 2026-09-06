"""Central settings configuration module for ResQtech.

Uses environment variables and optional .env file to load paths, geospatial boundaries,
and risk parameters without hardcoding local absolute paths.
"""

from pathlib import Path
from typing import Tuple
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base Directory: Project Root
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application Settings dataclass using Pydantic BaseSettings."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    APP_NAME: str = "ResQtech"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Directories
    DATA_RAW_DIR: Path = BASE_DIR / "data" / "raw"
    DATA_INTERIM_DIR: Path = BASE_DIR / "data" / "interim"
    DATA_PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    DATA_SAMPLES_DIR: Path = BASE_DIR / "data" / "samples"

    # Specific Dataset Paths
    GSI_DATA_DIR: Path = BASE_DIR / "data" / "raw" / "gsi"
    DEM_DATA_DIR: Path = BASE_DIR / "data" / "raw" / "dem"
    RAINFALL_DATA_DIR: Path = BASE_DIR / "data" / "raw" / "rainfall"
    SMAP_DATA_DIR: Path = BASE_DIR / "data" / "raw" / "smap"
    WORLDCOVER_DATA_DIR: Path = BASE_DIR / "data" / "raw" / "worldcover"

    MODELS_TRAINED_DIR: Path = BASE_DIR / "models" / "trained"
    MODELS_METADATA_DIR: Path = BASE_DIR / "models" / "metadata"

    # Bounding Box for North-Eastern Region (NER) of India
    # [min_lon, min_lat, max_lon, max_lat]
    NER_BBOX_MIN_LON: float = 87.8
    NER_BBOX_MIN_LAT: float = 21.9
    NER_BBOX_MAX_LON: float = 97.4
    NER_BBOX_MAX_LAT: float = 29.5

    # Projections
    CRS_GEOGRAPHIC: str = "EPSG:4326"
    CRS_PROJECTED_UTM: str = "EPSG:32646"  # UTM Zone 46N for NER

    # Prototype Thresholds (Subject to future scientific calibration)
    SUSCEPTIBILITY_HIGH_THRESHOLD: float = 0.70
    SUSCEPTIBILITY_MOD_THRESHOLD: float = 0.40

    TRIGGER_HIGH_THRESHOLD: float = 70.0
    TRIGGER_MOD_THRESHOLD: float = 40.0

    # Phase 7 Risk Fusion Parameters (Subject to future scientific calibration)
    FUSION_STATIC_WEIGHT: float = 0.50
    FUSION_DYNAMIC_WEIGHT: float = 0.50
    RISK_HIGH_THRESHOLD: float = 70.0
    RISK_MOD_THRESHOLD: float = 40.0
    STABLE_TREND_TOLERANCE: float = 2.0
    CALIBRATION_DISCLAIMER_TEXT: str = (
        "PROTOTYPE OPERATIONAL PARAMETERS — REQUIRES REGIONAL CALIBRATION"
    )

    # Satellite Processing Parameters (Phase 6)
    IMERG_PRECIP_VARIABLE: str = "precipitation"
    IMERG_FILL_VALUE: float = -9999.9
    SMAP_FILL_VALUE: float = -9999.0
    SMAP_VALID_MIN: float = 0.02
    SMAP_VALID_MAX: float = 0.50
    SMAP_NEAREST_DATE_TOLERANCE_DAYS: int = 0  # 0 means strict exact-date match

    @property
    def ner_bbox(self) -> Tuple[float, float, float, float]:
        """Returns NER bounding box as a tuple (min_lon, min_lat, max_lon, max_lat)."""
        return (
            self.NER_BBOX_MIN_LON,
            self.NER_BBOX_MIN_LAT,
            self.NER_BBOX_MAX_LON,
            self.NER_BBOX_MAX_LAT,
        )


def get_settings() -> Settings:
    """Factory function to retrieve global settings instance."""
    return Settings()
