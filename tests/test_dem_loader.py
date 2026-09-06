"""Unit tests for SRTM DEM Loader module.

Uses synthetic raster fixtures only. Synthetic fixtures are never mixed with
real project data or used for model training.
"""

from pathlib import Path
import zipfile
import numpy as np
import pytest

from src.data.loaders.dem_loader import (
    NODATA_VALUE,
    SRTMGL1_BYTE_SIZE,
    SRTMTileIndex,
    discover_srtm_archives,
    parse_tile_bounds,
    read_hgt_raster,
    safe_extract_archive,
)


def test_parse_tile_bounds():
    """Test parsing SRTM coordinates from standard tile filenames."""
    info_n = parse_tile_bounds("N20E087.SRTMGL1.hgt.zip")
    assert info_n["tile_id"] == "N20E087"
    assert info_n["south_lat"] == 20.0
    assert info_n["north_lat"] == 21.0
    assert info_n["west_lon"] == 87.0
    assert info_n["east_lon"] == 88.0
    assert info_n["expected_hgt"] == "N20E087.hgt"

    info_s = parse_tile_bounds("S12W045.hgt")
    assert info_s["tile_id"] == "S12W045"
    assert info_s["south_lat"] == -12.0
    assert info_s["north_lat"] == -11.0
    assert info_s["west_lon"] == -45.0
    assert info_s["east_lon"] == -44.0

    with pytest.raises(ValueError):
        parse_tile_bounds("invalid_filename.zip")


def test_safe_extract_archive_zip_slip_protection(tmp_path):
    """Test detection and blocking of path traversal vulnerabilities in zip members."""
    zip_file = tmp_path / "N20E087.SRTMGL1.hgt.zip"
    out_dir = tmp_path / "extracted"

    # Create a malicious zip file containing path traversal
    with zipfile.ZipFile(zip_file, "w") as zf:
        zf.writestr("../../malicious.hgt", b"fake_data")

    audit = safe_extract_archive(zip_file, output_dir=out_dir)
    assert audit["zip_valid"] is True
    assert audit["extraction_status"] == "failed_exception"
    assert "Path traversal detected" in audit["error_message"]


def test_safe_extract_archive_valid(tmp_path):
    """Test valid archive extraction and caching behavior."""
    zip_file = tmp_path / "N25E091.SRTMGL1.hgt.zip"
    out_dir = tmp_path / "extracted"

    # Create synthetic HGT data (3601 x 3601 int16)
    synthetic_hgt_bytes = np.full((3601, 3601), 500, dtype=">i2").tobytes()
    assert len(synthetic_hgt_bytes) == SRTMGL1_BYTE_SIZE

    with zipfile.ZipFile(zip_file, "w") as zf:
        zf.writestr("N25E091.hgt", synthetic_hgt_bytes)

    # First run: should extract
    audit1 = safe_extract_archive(zip_file, output_dir=out_dir)
    assert audit1["extraction_status"] == "extracted_success"
    assert (out_dir / "N25E091.hgt").exists()

    # Second run: should reuse cached file
    audit2 = safe_extract_archive(zip_file, output_dir=out_dir)
    assert audit2["extraction_status"] == "reused_cached"


def test_srtm_tile_index(tmp_path):
    """Test spatial tile index coordinate lookup."""
    index = SRTMTileIndex()
    
    info1 = parse_tile_bounds("N24E092.hgt")
    info2 = parse_tile_bounds("N25E092.hgt")

    index.add_tile(info1, tmp_path / "N24E092.hgt")
    index.add_tile(info2, tmp_path / "N25E092.hgt")

    # Inside N24E092
    tile_a = index.find_tile(24.45, 92.55)
    assert tile_a is not None
    assert tile_a["tile_id"] == "N24E092"

    # Inside N25E092
    tile_b = index.find_tile(25.10, 92.80)
    assert tile_b is not None
    assert tile_b["tile_id"] == "N25E092"

    # Uncovered coordinate
    tile_c = index.find_tile(10.0, 50.0)
    assert tile_c is None

    # NaN coordinate
    tile_nan = index.find_tile(np.nan, 92.5)
    assert tile_nan is None


def test_read_hgt_raster(tmp_path):
    """Test reading binary big-endian HGT file into 2D numpy array."""
    hgt_file = tmp_path / "N26E090.hgt"
    data = np.full((3601, 3601), 1250, dtype=">i2")
    data[0, 0] = NODATA_VALUE
    data.tofile(hgt_file)

    raster = read_hgt_raster(hgt_file)
    assert raster.shape == (3601, 3601)
    assert raster.dtype == np.dtype(">i2")
    assert raster[0, 0] == NODATA_VALUE
    assert raster[100, 100] == 1250
