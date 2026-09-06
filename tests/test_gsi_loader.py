"""Unit tests for GSI historical landslide inventory loader module.

Uses small synthetic test fixtures only. Synthetic fixtures are never mixed with
real project data or used for model training.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("geopandas", reason="SKIPPED — geopandas not installed in developer handover environment")
pytest.importorskip("pymupdf", reason="SKIPPED — pymupdf not installed in developer handover environment")

from src.data.loaders.gsi_loader import (
    clean_gsi_dataframe,
    filter_ner_records,
    generate_quality_report,
    normalize_state_name,
    parse_coordinate,
    validate_coordinates,
)


@pytest.fixture
def synthetic_raw_gsi_dataframe():
    """Create synthetic raw GSI dataframe for testing."""
    records = [
        # Header rows
        [1, "LANDSLIDE INVENTORY (Field vaidated)", None, None, None, None, None, None, None, None, None, None],
        [1, "Sl.No.", "Slide_No", "State", "District", "Slide_Name", "NH_SH_Location", "Latitude", "Longitude", "Material Involved", "Movement Type", "History"],
        # Valid Assam record
        [1, "1", "ASM/HKN/83D07/2020/2", "Assam", "Hailakandi", "Kukinala slide", "Kukinala", "24.27", "92.50", "Debris", "Slide", "NA"],
        # Valid Meghalaya record with multiline whitespace
        [2, "2", "MEG/SHL/2021/01", "Meghalay\n", "East Khasi Hills", "Shillong  slide", "NH44\n", "25.578", "91.893", "Earth", "Fall", "10 June 2020"],
        # Record with swapped coordinates
        [3, "3", "ASM/CHR/2020/003", "Assam", "Cachar", "Cachar Slide", "NH53", "93.045", "24.795", "Debris", "Slide", "NA"],
        # Record outside NER (e.g. Kerala)
        [4, "4", "KER/WAY/2020/01", "Kerala", "Wayanad", "Wayanad Slide", "SH1", "11.605", "76.083", "Rock", "Slide", "NA"],
        # Missing coordinates record
        [5, "5", "AS/DIM/2018/99", "Assam", "Karbi Anglong", "Unknown Slide", "NH39", "NA", "NA", "Debris", "Slide", "NA"],
        # Invalid coordinate record (out of bounds latitude > 90)
        [6, "6", "AR/TWA/2019/02", "Arunachal Pradesh", "Tawang", "Tawang Slide", "NH13", "125.4", "91.86", "Rock", "Fall", "NA"],
    ]
    cols = ["page_num", "sl_no", "slide_id", "state", "district", "slide_name", "road_location", "latitude", "longitude", "material_involved", "movement_type", "history"]
    return pd.DataFrame(records, columns=cols)


def test_normalize_state_name():
    """Test state name normalization handling spelling/case variations."""
    assert normalize_state_name("Assam") == "Assam"
    assert normalize_state_name("ASAM") == "Assam"
    assert normalize_state_name("ArunachalPradesh") == "Arunachal Pradesh"
    assert normalize_state_name("-Arunachal Pradesh") == "Arunachal Pradesh"
    assert normalize_state_name("Meghalay\n") == "Meghalaya"
    assert normalize_state_name(None) is None
    assert normalize_state_name("") is None


def test_parse_coordinate():
    """Test string to float coordinate parsing."""
    assert parse_coordinate("24.27") == 24.27
    assert parse_coordinate("  92.50\n") == 92.50
    assert parse_coordinate("25° 30'") == 25.0
    assert np.isnan(parse_coordinate("NA"))
    assert np.isnan(parse_coordinate(None))
    assert np.isnan(parse_coordinate("invalid"))


def test_clean_gsi_dataframe(synthetic_raw_gsi_dataframe):
    """Test column cleaning and header row removal."""
    df_clean = clean_gsi_dataframe(synthetic_raw_gsi_dataframe)
    
    # 2 header rows removed out of 8 total rows -> 6 data rows
    assert len(df_clean) == 6
    assert "LANDSLIDE INVENTORY" not in df_clean["sl_no"].values
    assert "Sl.No." not in df_clean["sl_no"].values
    
    # Test whitespace collapse
    megh_row = df_clean[df_clean["slide_id"] == "MEG/SHL/2021/01"].iloc[0]
    assert megh_row["state_clean"] == "Meghalaya"
    assert megh_row["slide_name"] == "Shillong slide"


def test_coordinate_validation(synthetic_raw_gsi_dataframe):
    """Test coordinate parsing and validation flag generation."""
    df_clean = clean_gsi_dataframe(synthetic_raw_gsi_dataframe)
    df_val = validate_coordinates(df_clean)

    # Missing coords
    missing_row = df_val[df_val["slide_id"] == "AS/DIM/2018/99"].iloc[0]
    assert bool(missing_row["coord_missing"]) is True
    assert bool(missing_row["is_valid_coord"]) is False

    # Swapped coords (lat=93.045, lon=24.795)
    swapped_row = df_val[df_val["slide_id"] == "ASM/CHR/2020/003"].iloc[0]
    assert bool(swapped_row["coord_swapped"]) is True

    # Impossible coords (lat=125.4)
    impossible_row = df_val[df_val["slide_id"] == "AR/TWA/2019/02"].iloc[0]
    assert bool(impossible_row["coord_impossible"]) is True
    assert bool(impossible_row["is_valid_coord"]) is False


def test_ner_filtering(synthetic_raw_gsi_dataframe):
    """Test state and spatial boundary filtering for NER target region."""
    df_clean = clean_gsi_dataframe(synthetic_raw_gsi_dataframe)
    df_val = validate_coordinates(df_clean)
    df_ner, df_non_ner = filter_ner_records(df_val)

    # Valid NER records should include Assam (24.27, 92.50) and Meghalaya (25.578, 91.893)
    assert len(df_ner) >= 2
    assert "Assam" in df_ner["state_clean"].values
    assert "Meghalaya" in df_ner["state_clean"].values
    
    # Non-NER should include Kerala record and records with missing/impossible coords
    assert "Kerala" in df_non_ner["state_clean"].values


def test_duplicate_handling(synthetic_raw_gsi_dataframe):
    """Test detection of duplicate slide_id candidates."""
    df_clean = clean_gsi_dataframe(synthetic_raw_gsi_dataframe)
    df_val = validate_coordinates(df_clean)
    df_ner, df_non_ner = filter_ner_records(df_val)
    
    report = generate_quality_report(synthetic_raw_gsi_dataframe, df_val, df_ner, df_non_ner)
    assert "duplicate_slide_id_count" in report
    assert "duplicate_coord_count" in report
