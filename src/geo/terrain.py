"""Terrain attribute derivation module.

Computes elevation and slope from SRTM DEM rasters using scientifically valid,
latitude-aware finite difference methods (Horn's algorithm).
"""

import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from src.data.loaders.dem_loader import NODATA_VALUE, SRTMGL1_DIM


def calculate_ground_spacing(lat_deg: float, pixel_res_deg: float = 1.0 / 3600.0) -> Tuple[float, float]:
    """Calculate ground spacing in meters for latitude (dy) and longitude (dx) degrees.

    Parameters
    ----------
    lat_deg : float
        Latitude in degrees.
    pixel_res_deg : float
        Pixel spatial resolution in degrees (default 1/3600 arc-sec for SRTM1).

    Returns
    -------
    Tuple[float, float]
        (dx_meters, dy_meters) ground spacing in meters.
    """
    # 1 degree latitude = ~111,320 meters on WGS84 ellipsoid
    meters_per_lat_deg = 111320.0
    dy_m = pixel_res_deg * meters_per_lat_deg

    # 1 degree longitude distance shrinks with cos(latitude)
    lat_rad = math.radians(lat_deg)
    dx_m = pixel_res_deg * meters_per_lat_deg * math.cos(lat_rad)

    return dx_m, dy_m


def compute_horn_slope_3x3(window_3x3: np.ndarray, dx_m: float, dy_m: float) -> float:
    """Calculate terrain slope in DEGREES from a 3x3 elevation window using Horn's algorithm.

    Window matrix convention:
    [[z11, z12, z13],
     [z21, z22, z23],
     [z31, z32, z33]]

    Parameters
    ----------
    window_3x3 : np.ndarray
        3x3 numpy array of elevation values in meters.
    dx_m : float
        Ground pixel width in meters (East-West).
    dy_m : float
        Ground pixel height in meters (North-South).

    Returns
    -------
    float
        Slope angle in degrees [0, 90], or np.nan if nodata encountered.
    """
    if window_3x3.shape != (3, 3):
        return np.nan

    # Check for nodata or suspicious invalid values (< -1000m)
    if np.any(window_3x3 == NODATA_VALUE) or np.any(window_3x3 < -1000):
        return np.nan

    z11, z12, z13 = window_3x3[0, 0], window_3x3[0, 1], window_3x3[0, 2]
    z21, z22, z23 = window_3x3[1, 0], window_3x3[1, 1], window_3x3[1, 2]
    z31, z32, z33 = window_3x3[2, 0], window_3x3[2, 1], window_3x3[2, 2]

    # Partial derivative along X (East-West)
    dz_dx = ((z13 + 2.0 * z23 + z33) - (z11 + 2.0 * z21 + z31)) / (8.0 * dx_m)

    # Partial derivative along Y (North-South)
    # Row 0 is North, Row 2 is South -> dz/dy = (South - North) / (8 * dy)
    dz_dy = ((z31 + 2.0 * z32 + z33) - (z11 + 2.0 * z12 + z13)) / (8.0 * dy_m)

    slope_magnitude = math.sqrt(dz_dx**2 + dz_dy**2)
    slope_rad = math.atan(slope_magnitude)
    slope_deg = math.degrees(slope_rad)

    return slope_deg


def compute_latitude_aware_slope_grid(
    elevation_grid: np.ndarray,
    center_lat: float,
    pixel_res_deg: float = 1.0 / 3600.0,
) -> np.ndarray:
    """Derive full 2D slope array in DEGREES from elevation grid using Horn's method.

    Parameters
    ----------
    elevation_grid : np.ndarray
        2D numpy array of elevation values in meters.
    center_lat : float
        Latitude of tile center for ground spacing calculation.
    pixel_res_deg : float
        Pixel spacing in degrees.

    Returns
    -------
    np.ndarray
        2D numpy array of float slope values in degrees. Boundary cells & nodata are NaN.
    """
    dx_m, dy_m = calculate_ground_spacing(center_lat, pixel_res_deg)
    rows, cols = elevation_grid.shape
    slope_grid = np.full((rows, cols), np.nan, dtype=np.float32)

    # Create padded elevation array to handle interior grid vectorized Horn calculation
    # Vectorized Horn calculation on valid interior cells
    z = elevation_grid.astype(np.float32)

    # Mask nodata values
    valid_mask = (z != NODATA_VALUE) & (z >= -1000)
    
    # 3x3 neighborhood slice views
    z11, z12, z13 = z[0:-2, 0:-2], z[0:-2, 1:-1], z[0:-2, 2:]
    z21, z22, z23 = z[1:-1, 0:-2], z[1:-1, 1:-1], z[1:-1, 2:]
    z31, z32, z33 = z[2:, 0:-2], z[2:, 1:-1], z[2:, 2:]

    # Check 3x3 validity mask
    m11, m12, m13 = valid_mask[0:-2, 0:-2], valid_mask[0:-2, 1:-1], valid_mask[0:-2, 2:]
    m21, m22, m23 = valid_mask[1:-1, 0:-2], valid_mask[1:-1, 1:-1], valid_mask[1:-1, 2:]
    m31, m32, m33 = valid_mask[2:, 0:-2], valid_mask[2:, 1:-1], valid_mask[2:, 2:]
    
    neighborhood_valid = m11 & m12 & m13 & m21 & m22 & m23 & m31 & m32 & m33

    dz_dx = ((z13 + 2.0 * z23 + z33) - (z11 + 2.0 * z21 + z31)) / (8.0 * dx_m)
    dz_dy = ((z31 + 2.0 * z32 + z33) - (z11 + 2.0 * z12 + z13)) / (8.0 * dy_m)

    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
    slope_deg_interior = np.degrees(slope_rad)

    slope_grid[1:-1, 1:-1] = np.where(neighborhood_valid, slope_deg_interior, np.nan)
    return slope_grid


def coord_to_pixel_indices(
    lat: float, lon: float, south_lat: float, west_lon: float, dim: int = SRTMGL1_DIM
) -> Tuple[int, int]:
    """Convert (lat, lon) coordinate to DEM raster (row, col) pixel indices.

    For SRTM:
    North boundary = south_lat + 1.0 (Row 0)
    South boundary = south_lat (Row 3600)
    West boundary = west_lon (Col 0)
    East boundary = west_lon + 1.0 (Col 3600)
    """
    north_lat = south_lat + 1.0
    lat_span = 1.0
    lon_span = 1.0

    row_float = ((north_lat - lat) / lat_span) * (dim - 1)
    col_float = ((lon - west_lon) / lon_span) * (dim - 1)

    row = int(round(row_float))
    col = int(round(col_float))

    row = max(0, min(dim - 1, row))
    col = max(0, min(dim - 1, col))

    return row, col


def sample_point_terrain(
    lat: float,
    lon: float,
    tile_info: Dict[str, Any],
    elevation_grid: np.ndarray,
) -> Dict[str, Any]:
    """Sample elevation and derive slope for a single (lat, lon) coordinate within an HGT tile.

    Parameters
    ----------
    lat : float
        Latitude coordinate.
    lon : float
        Longitude coordinate.
    tile_info : Dict[str, Any]
        Tile metadata dictionary containing south_lat, west_lon, etc.
    elevation_grid : np.ndarray
        2D numpy elevation raster array.

    Returns
    -------
    Dict[str, Any]
        Dictionary with elevation_m, slope_deg, elevation_valid, slope_valid.
    """
    dim = elevation_grid.shape[0]
    row, col = coord_to_pixel_indices(lat, lon, tile_info["south_lat"], tile_info["west_lon"], dim=dim)

    elev_val = float(elevation_grid[row, col])

    if elev_val == NODATA_VALUE or elev_val < -1000:
        elevation_m = np.nan
        elevation_valid = False
    else:
        elevation_m = elev_val
        elevation_valid = True

    # Extract 3x3 window around (row, col) for Horn slope
    # Handle tile border pixels by mirroring edge values if out-of-bounds
    r_min, r_max = row - 1, row + 2
    c_min, c_max = col - 1, col + 2

    # Pad or slice window
    if 0 <= r_min and r_max <= dim and 0 <= c_min and c_max <= dim:
        window = elevation_grid[r_min:r_max, c_min:c_max]
    else:
        # Edge cell: slice safely with border replication
        window = np.zeros((3, 3), dtype=elevation_grid.dtype)
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                rr = max(0, min(dim - 1, row + dr))
                cc = max(0, min(dim - 1, col + dc))
                window[dr + 1, dc + 1] = elevation_grid[rr, cc]

    dx_m, dy_m = calculate_ground_spacing(lat)
    slope_val = compute_horn_slope_3x3(window, dx_m, dy_m)

    if np.isnan(slope_val) or not elevation_valid:
        slope_deg = np.nan
        slope_valid = False
    else:
        slope_deg = float(slope_val)
        slope_valid = True

    return {
        "elevation_m": elevation_m,
        "slope_deg": slope_deg,
        "elevation_valid": elevation_valid,
        "slope_valid": slope_valid,
        "dem_tile": tile_info["tile_id"],
    }
