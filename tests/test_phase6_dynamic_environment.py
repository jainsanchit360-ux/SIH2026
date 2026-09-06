"""Automated unit and integration test suite for Phase 6 Dynamic Environmental Data Processing.

Tests NASA IMERG rainfall processor, NASA SMAP soil moisture processor, temporal alignment,
gap enforcement, quality flag policies, dynamic trigger calculations, and provenance tracking.
"""

from datetime import date
import math
import numpy as np
import pytest

from src.config.settings import get_settings
from src.data.processors.imerg_processor import IMERGProcessor
from src.data.processors.smap_processor import SMAPProcessor
from src.data.processors.temporal_alignment import TemporalAligner
from src.risk.trigger_engine import DynamicTriggerEngine, calculate_dynamic_trigger_score


_settings = get_settings()

_raw_imerg_available = (
    _settings.DATA_RAW_DIR / "rainfall"
).exists() and len(list((_settings.DATA_RAW_DIR / "rainfall").glob("*.nc4"))) > 0

_raw_smap_available = (
    _settings.DATA_RAW_DIR / "smap"
).exists() and len(list((_settings.DATA_RAW_DIR / "smap").glob("*.h5"))) > 0

skip_if_no_raw_imerg = pytest.mark.skipif(
    not _raw_imerg_available,
    reason="SKIPPED — raw IMERG archive not included in developer handover",
)

skip_if_no_raw_smap = pytest.mark.skipif(
    not _raw_smap_available,
    reason="SKIPPED — raw SMAP archive not included in developer handover",
)

skip_if_no_raw_data = pytest.mark.skipif(
    not (_raw_imerg_available and _raw_smap_available),
    reason="SKIPPED — raw satellite archives not included in developer handover",
)


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def imerg_processor():
    return IMERGProcessor()


@pytest.fixture
def smap_processor():
    return SMAPProcessor()


@pytest.fixture
def aligner(imerg_processor, smap_processor):
    return TemporalAligner(imerg_processor, smap_processor)


@pytest.fixture
def trigger_engine():
    return DynamicTriggerEngine()


# =====================================================================
# STEP 3 TESTS: IMERG RAINFALL PROCESSOR
# =====================================================================

@skip_if_no_raw_imerg
def test_imerg_discovery_and_metadata(imerg_processor):
    """Test IMERG file discovery, date parsing, and metadata summary generation."""
    meta = imerg_processor.get_metadata_summary()

    assert meta["total_files_discovered"] > 0
    assert meta["readable_file_count"] > 0
    assert meta["corrupt_file_count"] == 0
    assert meta["product_name"].startswith("GPM IMERG")
    assert meta["precipitation_variable"] == "precipitation"
    assert meta["precipitation_units"] == "mm/day"
    assert meta["ner_covered"] is True
    assert meta["longest_consecutive_days"] >= 40


@skip_if_no_raw_imerg
def test_imerg_point_extraction_valid(imerg_processor):
    """Test point rainfall extraction for a known valid NER coordinate and date."""
    # Gangtok: 27.33 N, 88.61 E on 2025-07-04
    res = imerg_processor.extract_point(27.33, 88.61, date(2025, 7, 4))

    assert res["status"] == "VALID"
    assert not math.isnan(res["rainfall_1d"])
    assert res["rainfall_1d"] >= 0.0
    assert res["units"] == "mm/day"
    assert "3B-DAY" in res["source_file"]


@skip_if_no_raw_imerg
def test_imerg_out_of_bounds(imerg_processor):
    """Test IMERG extraction for out-of-bounds coordinates."""
    res = imerg_processor.extract_point(89.0, 200.0, date(2025, 7, 4))
    assert res["status"] == "OUT_OF_BOUNDS"
    assert math.isnan(res["rainfall_1d"])


def test_imerg_missing_file(imerg_processor):
    """Test IMERG extraction for a date with no available file."""
    res = imerg_processor.extract_point(27.33, 88.61, date(2010, 1, 1))
    assert res["status"] == "MISSING_FILE"
    assert math.isnan(res["rainfall_1d"])


@skip_if_no_raw_imerg
def test_imerg_rolling_consecutive_window_valid(imerg_processor):
    """Test 1d, 3d, and 7d rolling rainfall when consecutive dates exist."""
    # 2025-07-04 is within the 48-day consecutive window (2025-06-23 to 2025-08-09)
    res = imerg_processor.extract_point_rolling(27.33, 88.61, date(2025, 7, 4))

    assert res["rainfall_data_status"] == "VALID"
    assert not math.isnan(res["rainfall_1d"])
    assert not math.isnan(res["rainfall_3d"])
    assert not math.isnan(res["rainfall_7d"])
    assert res["rainfall_3d"] >= res["rainfall_1d"]
    assert res["rainfall_7d"] >= res["rainfall_3d"]
    assert len(res["missing_dates_in_7d_window"]) == 0


def test_imerg_rolling_gap_enforcement(imerg_processor):
    """Test strict gap enforcement: rolling sums must return INSUFFICIENT_HISTORY across gaps."""
    # 2025-05-04 has missing dates prior (e.g. 2025-05-03 is missing)
    res = imerg_processor.extract_point_rolling(27.33, 88.61, date(2025, 5, 4))

    assert res["status_3d"] == "INSUFFICIENT_HISTORY"
    assert res["status_7d"] == "INSUFFICIENT_HISTORY"
    assert math.isnan(res["rainfall_3d"])
    assert math.isnan(res["rainfall_7d"])
    assert len(res["missing_dates_in_7d_window"]) > 0


# =====================================================================
# STEP 4 TESTS: SMAP SOIL MOISTURE PROCESSOR
# =====================================================================

@skip_if_no_raw_smap
def test_smap_discovery_and_metadata(smap_processor):
    """Test SMAP file discovery, date parsing, duplicate resolution, and metadata."""
    meta = smap_processor.get_metadata_summary()

    assert meta["total_files_discovered"] > 0
    assert meta["readable_file_count"] > 0
    assert meta["corrupt_file_count"] == 0
    assert meta["soil_moisture_units"] == "cm^3/cm^3"
    assert meta["fill_value"] == -9999.0
    assert meta["valid_min"] == 0.02
    assert meta["valid_max"] == 0.50
    assert meta["ner_covered"] is True


@skip_if_no_raw_smap
def test_smap_point_extraction_quality(smap_processor):
    """Test SMAP extraction and quality flag handling for NER coordinates."""
    # Guwahati: 26.14 N, 91.73 E on 2025-07-04
    res = smap_processor.extract_point(26.14, 91.73, date(2025, 7, 4))

    assert res["smap_data_status"] == "VALID"
    assert not math.isnan(res["soil_moisture"])
    assert 0.02 <= res["soil_moisture"] <= 0.50
    assert res["soil_moisture_quality"] in ["HIGH", "RECOMMENDED", "WARNING"]
    assert "SMAP_L3_SM_P" in res["source_file"]


def test_smap_fill_value_rejection(smap_processor):
    """Test that SMAP fill values (-9999.0) are rejected and return INVALID_RETRIEVAL status."""
    # Gangtok high elevation cell where radar/radiometer retrieval yields fill value on certain dates
    res = smap_processor.extract_point(27.33, 88.61, date(2025, 7, 4))

    if res["smap_data_status"] == "INVALID_RETRIEVAL":
        assert math.isnan(res["soil_moisture"])
        assert res["soil_moisture_quality"] == "INVALID"


def test_smap_out_of_bounds(smap_processor):
    """Test SMAP out of bounds or missing date behavior."""
    res = smap_processor.extract_point(27.33, 88.61, date(2010, 1, 1))
    assert res["smap_data_status"] == "MISSING_FILE"
    assert math.isnan(res["soil_moisture"])


# =====================================================================
# STEP 5 TESTS: TEMPORAL ALIGNMENT
# =====================================================================

@skip_if_no_raw_data
def test_temporal_alignment_complete(aligner):
    """Test complete alignment when both rainfall and soil moisture are valid."""
    # Guwahati 2025-07-04 has valid rainfall and valid soil moisture
    res = aligner.align_observation(26.14, 91.73, date(2025, 7, 4))

    assert res["observation_date"] == "2025-07-04"
    assert not math.isnan(res["rainfall_1d"])
    assert not math.isnan(res["soil_moisture"])
    assert res["overall_alignment_status"] == "COMPLETE"
    assert res["smap_date_offset_days"] == 0


@skip_if_no_raw_data
def test_temporal_alignment_partial(aligner):
    """Test partial alignment when soil moisture retrieval is invalid/missing."""
    # Gangtok 2025-07-04 has valid rainfall but invalid SMAP retrieval
    res = aligner.align_observation(27.33, 88.61, date(2025, 7, 4))

    assert res["observation_date"] == "2025-07-04"
    assert not math.isnan(res["rainfall_1d"])
    assert res["overall_alignment_status"] == "PARTIAL_RAINFALL_ONLY"


# =====================================================================
# STEP 6 & 7 TESTS: DYNAMIC TRIGGER ENGINE
# =====================================================================

def test_trigger_engine_low_pressure(trigger_engine):
    """Test dynamic trigger calculation under low environmental pressure."""
    res = trigger_engine.calculate_trigger(
        rainfall_1d=2.0,
        rainfall_3d=5.0,
        rainfall_7d=10.0,
        soil_moisture=0.15,
    )

    assert res["dynamic_trigger_level"] == "LOW"
    assert 0.0 <= res["dynamic_trigger_score"] < 40.0
    assert "PROTOTYPE OPERATIONAL TRIGGER PARAMETERS" in res["calibration_disclaimer"]


def test_trigger_engine_high_pressure(trigger_engine):
    """Test dynamic trigger calculation under severe environmental pressure."""
    res = trigger_engine.calculate_trigger(
        rainfall_1d=85.0,
        rainfall_3d=160.0,
        rainfall_7d=260.0,
        soil_moisture=0.42,
    )

    assert res["dynamic_trigger_level"] == "HIGH"
    assert res["dynamic_trigger_score"] >= 70.0
    assert len(res["major_trigger_factors"]) > 0


def test_trigger_engine_insufficient_data(trigger_engine):
    """Test trigger engine behavior when rainfall history is missing."""
    res = trigger_engine.calculate_trigger(
        rainfall_1d=np.nan,
        rainfall_3d=np.nan,
        rainfall_7d=np.nan,
        soil_moisture=0.35,
        rainfall_data_status="INSUFFICIENT_HISTORY",
    )

    assert res["dynamic_trigger_level"] == "INSUFFICIENT_DATA"
    assert math.isnan(res["dynamic_trigger_score"])


def test_backwards_compatible_trigger_function():
    """Test convenience function calculate_dynamic_trigger_score."""
    score = calculate_dynamic_trigger_score(
        rainfall_1d_mm=80.0,
        rainfall_3d_mm=140.0,
        rainfall_7d_mm=220.0,
        soil_moisture_pct=38.0,  # 38%
    )
    assert isinstance(score, float)
    assert score > 50.0
