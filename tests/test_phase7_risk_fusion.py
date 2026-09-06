"""Automated Unit and Integration Test Suite for Phase 7 Risk Fusion Engine.

Tests static susceptibility interface, dynamic trigger reuse, deterministic fusion equation,
risk level thresholds, missing & partial data failure policies, score clipping bounds,
explainability generation, risk trend tracking, simulated demo mode, and dataset schemas.
"""

import math
import numpy as np
import pandas as pd
import pytest

from src.config.settings import get_settings
from src.risk.susceptibility import StaticSusceptibilityEngine, calculate_static_susceptibility_score
from src.risk.trigger_engine import DynamicTriggerEngine, calculate_dynamic_trigger_score
from src.risk.risk_fusion import RiskFusionEngine, fuse_risk_layers
from src.risk.demo_simulation import simulate_dynamic_risk_scenario


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def static_engine():
    return StaticSusceptibilityEngine()


@pytest.fixture
def trigger_engine():
    return DynamicTriggerEngine()


@pytest.fixture
def fusion_engine():
    return RiskFusionEngine()


# =====================================================================
# STEP 2 TESTS: STATIC SUSCEPTIBILITY INTERFACE
# =====================================================================

def test_static_susceptibility_interface_valid(static_engine):
    """Test static susceptibility evaluation for a valid NER coordinate."""
    res = static_engine.evaluate_static_susceptibility(
        latitude=27.33,
        longitude=88.61,
        elevation_m=1450.0,
        slope_deg=32.0,
        historical_count_5km=15,
        historical_count_10km=45,
    )

    assert res["latitude"] == 27.33
    assert res["longitude"] == 88.61
    assert not math.isnan(res["static_susceptibility_score"])
    assert 0.0 <= res["static_susceptibility_score"] <= 100.0
    assert res["static_susceptibility_level"] in ["LOW", "MODERATE", "HIGH"]
    assert "1.1.0-phase5b" in res["static_model_version"]
    assert "elevation_m" in res["static_model_features"]
    assert len(res["static_major_factors"]) > 0
    assert res["static_data_status"] == "VALID"
    assert "PROTOTYPE OPERATIONAL PARAMETERS" in res["calibration_disclaimer"]


def test_static_susceptibility_out_of_bounds(static_engine):
    """Test static susceptibility interface for out-of-bounds coordinate."""
    res = static_engine.evaluate_static_susceptibility(latitude=0.0, longitude=0.0)

    assert res["static_data_status"] == "OUT_OF_BOUNDS"
    assert res["static_susceptibility_level"] == "INSUFFICIENT_DATA"
    assert math.isnan(res["static_susceptibility_score"])


def test_static_susceptibility_missing_data(static_engine):
    """Test static susceptibility interface when input predictors are missing."""
    res = static_engine.evaluate_static_susceptibility(
        latitude=26.14,
        longitude=91.73,
        elevation_m=np.nan,
        slope_deg=np.nan,
    )

    assert res["static_data_status"] == "MISSING_DATA"
    assert res["static_susceptibility_level"] == "INSUFFICIENT_DATA"
    assert math.isnan(res["static_susceptibility_score"])


def test_backwards_compatible_static_function():
    """Test convenience calculate_static_susceptibility_score function."""
    score = calculate_static_susceptibility_score(
        elevation_m=1200.0,
        slope_deg=28.0,
        landslide_density_5km=10.0,
        latitude=27.0,
        longitude=92.0,
    )
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


# =====================================================================
# STEP 3 TESTS: DYNAMIC TRIGGER REUSE
# =====================================================================

def test_dynamic_trigger_interface_reuse(trigger_engine):
    """Test reuse of DynamicTriggerEngine with Phase 7 output schema."""
    res = trigger_engine.calculate_trigger(
        rainfall_1d=45.0,
        rainfall_3d=85.0,
        rainfall_7d=130.0,
        soil_moisture=0.32,
        observation_date="2025-07-04",
        source_provenance="NASA IMERG + SMAP",
    )

    assert res["observation_date"] == "2025-07-04"
    assert res["rainfall_1d"] == 45.0
    assert not math.isnan(res["dynamic_trigger_score"])
    assert res["dynamic_trigger_level"] in ["LOW", "MODERATE", "HIGH"]
    assert len(res["dynamic_major_factors"]) > 0
    assert res["dynamic_data_status"] == "VALID"
    assert res["source_provenance"] == "NASA IMERG + SMAP"


# =====================================================================
# STEP 4 & 5 TESTS: FUSION FORMULA & RISK LEVEL THRESHOLDS
# =====================================================================

def test_risk_fusion_formula_and_thresholds(fusion_engine, static_engine, trigger_engine):
    """Test deterministic weighted fusion equation and threshold levels."""
    # Static score 80 (HIGH), Dynamic score 80 (HIGH) -> Fused = 80 (HIGH)
    static_res = static_engine.evaluate_static_susceptibility(27.33, 88.61, 1400.0, 30.0, 20.0, 50.0)
    trig_res = trigger_engine.calculate_trigger(90.0, 160.0, 250.0, 0.42, observation_date="2025-07-04")

    fused = fusion_engine.fuse(static_res, trig_res)

    expected = round(0.5 * static_res["static_susceptibility_score"] + 0.5 * trig_res["dynamic_trigger_score"], 2)
    assert fused["current_risk_score"] == expected
    assert fused["current_risk_level"] == "HIGH"
    assert 0.0 <= fused["current_risk_score"] <= 100.0


def test_risk_level_threshold_boundaries(fusion_engine):
    """Test exact threshold boundary classifications (LOW, MODERATE, HIGH)."""
    assert fusion_engine.classify_risk_level(20.0) == "LOW"
    assert fusion_engine.classify_risk_level(39.9) == "LOW"
    assert fusion_engine.classify_risk_level(40.0) == "MODERATE"
    assert fusion_engine.classify_risk_level(69.9) == "MODERATE"
    assert fusion_engine.classify_risk_level(70.0) == "HIGH"
    assert fusion_engine.classify_risk_level(95.0) == "HIGH"


# =====================================================================
# STEP 6 TESTS: DATA COMPLETENESS & FAILURE POLICY
# =====================================================================

def test_missing_static_returns_insufficient_data(fusion_engine, trigger_engine):
    """Test that missing static susceptibility returns INSUFFICIENT_DATA."""
    static_missing = {
        "latitude": 26.0,
        "longitude": 91.0,
        "static_susceptibility_score": np.nan,
        "static_data_status": "MISSING_DATA",
    }
    trig_res = trigger_engine.calculate_trigger(50.0, 80.0, 120.0, 0.30)

    fused = fusion_engine.fuse(static_missing, trig_res)

    assert fused["current_risk_level"] == "INSUFFICIENT_DATA"
    assert math.isnan(fused["current_risk_score"])
    assert fused["data_completeness"]["confidence_status"] == "INSUFFICIENT_DATA"


def test_missing_dynamic_rainfall_returns_insufficient_data(fusion_engine, static_engine):
    """Test that fully missing dynamic rainfall returns INSUFFICIENT_DATA."""
    static_res = static_engine.evaluate_static_susceptibility(27.33, 88.61, 1400.0, 30.0, 20.0, 50.0)
    trig_missing = {
        "dynamic_trigger_score": np.nan,
        "dynamic_trigger_level": "INSUFFICIENT_DATA",
        "dynamic_data_status": "INSUFFICIENT_DATA",
    }

    fused = fusion_engine.fuse(static_res, trig_missing)

    assert fused["current_risk_level"] == "INSUFFICIENT_DATA"
    assert math.isnan(fused["current_risk_score"])


def test_partial_dynamic_soil_moisture_degraded_confidence(fusion_engine, static_engine, trigger_engine):
    """Test that missing soil moisture computes degraded score with explicit status tag."""
    static_res = static_engine.evaluate_static_susceptibility(27.33, 88.61, 1400.0, 30.0, 20.0, 50.0)
    # Valid rainfall but missing SMAP soil moisture (NaN)
    trig_partial = trigger_engine.calculate_trigger(
        rainfall_1d=60.0,
        rainfall_3d=110.0,
        rainfall_7d=180.0,
        soil_moisture=np.nan,
        soil_moisture_data_status="INVALID_RETRIEVAL",
    )

    fused = fusion_engine.fuse(static_res, trig_partial)

    assert not math.isnan(fused["current_risk_score"])
    assert fused["current_risk_level"] in ["LOW", "MODERATE", "HIGH"]
    assert fused["data_completeness"]["confidence_status"] == "DEGRADED_CONFIDENCE_RAINFALL_ONLY"
    assert "soil_moisture" in fused["data_completeness"]["missing_inputs"]


# =====================================================================
# STEP 7 & 9 TESTS: EXPLAINABILITY & TREND SUPPORT
# =====================================================================

def test_explainability_narrative_generation(fusion_engine, static_engine, trigger_engine):
    """Test rich narrative and risk driver generation."""
    static_res = static_engine.evaluate_static_susceptibility(27.33, 88.61, 1400.0, 32.0, 25.0, 60.0)
    trig_res = trigger_engine.calculate_trigger(80.0, 140.0, 220.0, 0.40, observation_date="2025-07-04")

    fused = fusion_engine.fuse(static_res, trig_res)

    assert len(fused["major_risk_factors"]) > 0
    assert len(fused["static_contributors"]) > 0
    assert len(fused["dynamic_contributors"]) > 0
    assert "Current Risk" in fused["risk_explanation"]


def test_trend_calculation_and_what_changed(fusion_engine, static_engine, trigger_engine):
    """Test sequential date trend calculation (RISING, FALLING, STABLE, UNKNOWN) and what_changed."""
    static_res = static_engine.evaluate_static_susceptibility(27.33, 88.61, 1400.0, 25.0, 10.0, 30.0)

    # Date 1: Moderate trigger (Score ~50)
    trig_d1 = trigger_engine.calculate_trigger(30.0, 50.0, 80.0, 0.25, observation_date="2025-07-04")
    fused_d1 = fusion_engine.fuse(static_res, trig_d1)

    assert fused_d1["risk_trend"] == "UNKNOWN"

    # Date 2: Heavy rainfall spike (Score ~85)
    trig_d2 = trigger_engine.calculate_trigger(95.0, 180.0, 280.0, 0.44, observation_date="2025-07-05")
    fused_d2 = fusion_engine.fuse(
        static_res,
        trig_d2,
        previous_risk_score=fused_d1["current_risk_score"],
        previous_risk_level=fused_d1["current_risk_level"],
    )

    assert fused_d2["previous_risk_score"] == fused_d1["current_risk_score"]
    assert fused_d2["risk_score_change"] > 5.0
    assert fused_d2["risk_trend"] == "RISING"
    assert "increased" in fused_d2["what_changed"].lower()


# =====================================================================
# STEP 10 TESTS: DEMO SIMULATION LAYER
# =====================================================================

def test_demo_simulation_mode(static_engine):
    """Test controlled demo simulation layer isolated from real satellite records."""
    baseline = {
        "site_id": "NER_PILOT_01",
        "site_name": "Gangtok, Sikkim",
        "state": "Sikkim",
        "latitude": 27.33,
        "longitude": 88.61,
        "elevation_m": 1445.0,
        "slope_deg": 33.5,
        "historical_count_5km": 28,
        "historical_count_10km": 100,
        "current_risk_score": 45.0,
        "current_risk_level": "MODERATE",
    }

    # Simulate heavy rainfall spike
    sim_fused = simulate_dynamic_risk_scenario(
        baseline_location_record=baseline,
        simulated_rainfall_1d=110.0,
        simulated_rainfall_3d=190.0,
        simulated_rainfall_7d=300.0,
        simulated_soil_moisture=0.45,
        scenario_name="Extreme Monsoon Cloudburst",
    )

    assert sim_fused["simulation_mode"] is True
    assert sim_fused["data_source"] == "SIMULATED_DEMO"
    assert sim_fused["current_risk_level"] == "HIGH"
    assert sim_fused["current_risk_score"] > baseline["current_risk_score"]
    assert "[DEMO SIMULATION:" in sim_fused["risk_explanation"]


# =====================================================================
# STEP 8 & 11 TESTS: PROCESSED FUSED DATASET SCHEMA
# =====================================================================

def test_fused_parquet_dataset_exists_and_valid(settings):
    """Test that generated current_landslide_risk.parquet exists with complete schema."""
    parquet_path = settings.DATA_PROCESSED_DIR / "current_landslide_risk.parquet"
    assert parquet_path.exists()

    df = pd.read_parquet(parquet_path)
    assert len(df) > 0

    required_cols = [
        "site_id", "latitude", "longitude", "observation_date",
        "static_susceptibility_score", "static_susceptibility_level",
        "rainfall_1d", "rainfall_3d", "rainfall_7d", "soil_moisture",
        "dynamic_trigger_score", "dynamic_trigger_level",
        "current_risk_score", "current_risk_level",
        "risk_trend", "risk_explanation", "calibration_disclaimer",
    ]

    for col in required_cols:
        assert col in df.columns, f"Missing required column in parquet: {col}"

    levels = set(df["current_risk_level"].unique())
    assert "LOW" in levels
    assert "MODERATE" in levels
    assert "HIGH" in levels
    assert "INSUFFICIENT_DATA" in levels
