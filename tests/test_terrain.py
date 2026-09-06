"""Unit tests for terrain attribute derivation module.

Uses synthetic raster fixtures only. Synthetic fixtures are never mixed with
real project data or used for model training.
"""

import math
import numpy as np
import pytest

from src.data.loaders.dem_loader import NODATA_VALUE, SRTMGL1_DIM
from src.geo.terrain import (
    calculate_ground_spacing,
    compute_horn_slope_3x3,
    compute_latitude_aware_slope_grid,
    coord_to_pixel_indices,
    sample_point_terrain,
)


def test_calculate_ground_spacing():
    """Test latitude-aware ground spacing calculation in meters."""
    # Equator (lat 0): cos(0) = 1.0 -> dx == dy
    dx_eq, dy_eq = calculate_ground_spacing(0.0)
    assert pytest.approx(dx_eq, rel=1e-5) == dy_eq
    assert pytest.approx(dy_eq, rel=1e-3) == (1.0 / 3600.0) * 111320.0  # ~30.92m

    # 60 degrees North: cos(60) = 0.5 -> dx == 0.5 * dy
    dx_60, dy_60 = calculate_ground_spacing(60.0)
    assert pytest.approx(dx_60, rel=1e-4) == 0.5 * dy_60


def test_compute_horn_slope_flat_surface():
    """Test slope of a perfectly flat elevation surface is 0.0 degrees."""
    flat_window = np.full((3, 3), 500.0, dtype=np.float32)
    dx_m, dy_m = calculate_ground_spacing(25.0)

    slope_deg = compute_horn_slope_3x3(flat_window, dx_m, dy_m)
    assert pytest.approx(slope_deg, abs=1e-5) == 0.0


def test_compute_horn_slope_45_degree_ramp():
    """Test slope of a 45-degree elevation ramp (dz/dx = 1.0)."""
    dx_m = 30.0
    dy_m = 30.0

    # dz/dx = 1.0 -> elevation increases by 30 meters per pixel (30m) along East
    ramp_window = np.array(
        [
            [0.0, 30.0, 60.0],
            [0.0, 30.0, 60.0],
            [0.0, 30.0, 60.0],
        ],
        dtype=np.float32,
    )

    slope_deg = compute_horn_slope_3x3(ramp_window, dx_m, dy_m)
    assert pytest.approx(slope_deg, abs=1e-3) == 45.0


def test_compute_horn_slope_nodata():
    """Test slope calculation returns NaN if nodata value present in 3x3 window."""
    window_with_nodata = np.full((3, 3), 500.0, dtype=np.float32)
    window_with_nodata[1, 1] = float(NODATA_VALUE)
    dx_m, dy_m = calculate_ground_spacing(25.0)

    slope_deg = compute_horn_slope_3x3(window_with_nodata, dx_m, dy_m)
    assert np.isnan(slope_deg)


def test_compute_latitude_aware_slope_grid():
    """Test 2D slope grid derivation on a synthetic elevation grid."""
    grid = np.full((10, 10), 100.0, dtype=np.int16)
    slope_grid = compute_latitude_aware_slope_grid(grid, center_lat=26.0)

    assert slope_grid.shape == (10, 10)
    # Interior 8x8 should be 0.0 degrees
    assert np.allclose(slope_grid[1:-1, 1:-1], 0.0, atol=1e-4)
    # Edge cells should be NaN
    assert np.isnan(slope_grid[0, 0])
    assert np.isnan(slope_grid[-1, -1])


def test_coord_to_pixel_indices():
    """Test conversion of (lat, lon) coordinates to raster row/col indices."""
    south_lat = 24.0
    west_lon = 92.0
    dim = 3601

    # Northwest corner (25.0, 92.0) -> row 0, col 0
    r1, c1 = coord_to_pixel_indices(25.0, 92.0, south_lat, west_lon, dim=dim)
    assert r1 == 0 and c1 == 0

    # Southwest corner (24.0, 92.0) -> row 3600, col 0
    r2, c2 = coord_to_pixel_indices(24.0, 92.0, south_lat, west_lon, dim=dim)
    assert r2 == 3600 and c2 == 0

    # Center point (24.5, 92.5) -> row 1800, col 1800
    r3, c3 = coord_to_pixel_indices(24.5, 92.5, south_lat, west_lon, dim=dim)
    assert r3 == 1800 and c3 == 1800


def test_sample_point_terrain():
    """Test sampling elevation and deriving slope for a specific point."""
    tile_info = {
        "tile_id": "N24E092",
        "south_lat": 24.0,
        "north_lat": 25.0,
        "west_lon": 92.0,
        "east_lon": 93.0,
    }

    grid = np.full((3601, 3601), 350, dtype=">i2")
    
    # Valid point in center
    result = sample_point_terrain(24.5, 92.5, tile_info, grid)
    assert result["elevation_m"] == 350.0
    assert result["elevation_valid"] is True
    assert pytest.approx(result["slope_deg"], abs=1e-4) == 0.0
    assert result["slope_valid"] is True
    assert result["dem_tile"] == "N24E092"

    # Point with nodata
    grid[1800, 1800] = NODATA_VALUE
    result_nodata = sample_point_terrain(24.5, 92.5, tile_info, grid)
    assert np.isnan(result_nodata["elevation_m"])
    assert result_nodata["elevation_valid"] is False
    assert np.isnan(result_nodata["slope_deg"])
    assert result_nodata["slope_valid"] is False
