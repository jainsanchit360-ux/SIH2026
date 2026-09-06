"""Spatial feature extraction module.

Computes spatial proximity, historical landslide point density, nearest-neighbor distances,
and self-exclusion logic for spatial susceptibility dataset construction.
"""

import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

EARTH_RADIUS_METERS = 6371000.0


def haversine_distance_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Compute Haversine distance in meters between two lat/lon points.

    Parameters
    ----------
    lat1, lon1 : float
        Latitude and longitude of first point in degrees.
    lat2, lon2 : float
        Latitude and longitude of second point in degrees.

    Returns
    -------
    float
        Geodesic distance in meters.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c


def compute_historical_features(
    query_df: pd.DataFrame,
    reference_landslides_df: pd.DataFrame,
    self_exclusion: bool = False,
    radii_km: List[float] = [1.0, 2.0, 5.0, 10.0],
    lat_col: str = "lat_num",
    lon_col: str = "lon_num",
) -> pd.DataFrame:
    """Compute historical landslide proximity and density features for query points.

    Implements:
    1. Nearest landslide distance (nearest_landslide_distance_m)
    2. Historical landslide counts within radius (historical_count_Xkm)
    3. Unique-coordinate historical counts within radius (unique_historical_count_Xkm)
    4. Self-Exclusion: If query_df is the reference dataset itself and self_exclusion=True,
       excludes the query observation itself so self-distance is not 0m.

    Parameters
    ----------
    query_df : pd.DataFrame
        Query coordinates DataFrame containing lat_col and lon_col.
    reference_landslides_df : pd.DataFrame
        Reference historical landslide DataFrame containing lat_col and lon_col.
    self_exclusion : bool
        If True, exclude self-match when query point is present in reference dataset.
    radii_km : List[float]
        Radii in kilometers for spatial density counting.
    lat_col : str
        Latitude column name.
    lon_col : str
        Longitude column name.

    Returns
    -------
    pd.DataFrame
        DataFrame with spatial context feature columns.
    """
    ref_valid = reference_landslides_df.dropna(subset=[lat_col, lon_col]).copy()
    if len(ref_valid) == 0:
        raise ValueError("Reference landslide dataset contains no valid coordinates.")

    # Convert coordinates to radians for BallTree (lat, lon)
    ref_coords_rad = np.radians(ref_valid[[lat_col, lon_col]].to_numpy())

    # Build spatial index using Haversine metric
    tree = BallTree(ref_coords_rad, metric="haversine")

    query_coords_rad = np.radians(query_df[[lat_col, lon_col]].to_numpy())
    n_queries = len(query_df)

    # Output feature arrays
    nearest_dist_m = np.full(n_queries, np.nan, dtype=np.float64)
    density_counts = {f"historical_count_{int(r)}km": np.zeros(n_queries, dtype=np.int32) for r in radii_km}
    unique_density_counts = {f"unique_historical_count_{int(r)}km": np.zeros(n_queries, dtype=np.int32) for r in radii_km if r in [1.0, 5.0]}

    # 1. Nearest Neighbor Distance
    # Query k=2 if self_exclusion else k=1
    k_neighbors = 2 if self_exclusion else 1
    k_actual = min(k_neighbors, len(ref_valid))
    distances_rad, indices = tree.query(query_coords_rad, k=k_actual)

    for i in range(n_queries):
        if self_exclusion and k_actual > 1:
            # Check if 1st nearest neighbor distance is ~0 (self-match)
            d0_m = distances_rad[i, 0] * EARTH_RADIUS_METERS
            if d0_m < 0.1:  # Self match < 10cm
                dist_val = distances_rad[i, 1] * EARTH_RADIUS_METERS
            else:
                dist_val = d0_m
        else:
            dist_val = distances_rad[i, 0] * EARTH_RADIUS_METERS

        nearest_dist_m[i] = dist_val

    # 2. Radius Counts
    ref_lat_arr = ref_valid[lat_col].to_numpy()
    ref_lon_arr = ref_valid[lon_col].to_numpy()

    for r_km in radii_km:
        r_m = r_km * 1000.0
        r_rad = r_m / EARTH_RADIUS_METERS
        
        # Returns array of neighbor index arrays for each query
        neighbor_indices_list = tree.query_radius(query_coords_rad, r=r_rad, return_distance=False)
        col_name = f"historical_count_{int(r_km)}km"
        has_unique = r_km in [1.0, 5.0]
        unique_col_name = f"unique_historical_count_{int(r_km)}km"

        for i in range(n_queries):
            idx_list = neighbor_indices_list[i]
            
            if self_exclusion:
                # Filter out self-match if present
                q_lat = query_df.iloc[i][lat_col]
                q_lon = query_df.iloc[i][lon_col]
                
                valid_idxs = []
                for n_idx in idx_list:
                    n_lat = ref_lat_arr[n_idx]
                    n_lon = ref_lon_arr[n_idx]
                    if abs(q_lat - n_lat) > 1e-7 or abs(q_lon - n_lon) > 1e-7:
                        valid_idxs.append(n_idx)
                idx_list = np.array(valid_idxs, dtype=int)

            density_counts[col_name][i] = len(idx_list)

            if has_unique:
                if len(idx_list) > 0:
                    coords = set(zip(ref_lat_arr[idx_list], ref_lon_arr[idx_list]))
                    unique_density_counts[unique_col_name][i] = len(coords)
                else:
                    unique_density_counts[unique_col_name][i] = 0

    # Assemble result DataFrame
    res_df = pd.DataFrame({"nearest_landslide_distance_m": nearest_dist_m}, index=query_df.index)
    for col_name, arr in density_counts.items():
        res_df[col_name] = arr
    for col_name, arr in unique_density_counts.items():
        res_df[col_name] = arr

    return res_df
