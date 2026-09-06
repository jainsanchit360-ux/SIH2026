"""Static feature engineering and dataset assembly module.

Combines positive historical GSI observations and background control samples,
computes spatial block IDs for spatial cross-validation, and organizes static predictor features.
"""

import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


def assign_spatial_blocks(df: pd.DataFrame, grid_size_deg: float = 0.3) -> pd.Series:
    """Assign geographic block identifiers (spatial_block_id) for spatial cross-validation.

    Divides the region into ~30 km x 30 km (0.3 degree) geographic grid blocks.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with lat_num and lon_num columns.
    grid_size_deg : float
        Grid block size in degrees.

    Returns
    -------
    pd.Series
        Series of string spatial_block_id values.
    """
    lat_idx = np.floor(df["lat_num"] / grid_size_deg).astype(int)
    lon_idx = np.floor(df["lon_num"] / grid_size_deg).astype(int)

    block_ids = [
        f"BLOCK_N{lat:03d}_E{lon:03d}" for lat, lon in zip(lat_idx, lon_idx)
    ]
    return pd.Series(block_ids, index=df.index)


def assemble_susceptibility_dataset(
    positives_df: pd.DataFrame,
    background_df: pd.DataFrame,
    pos_spatial_features: pd.DataFrame,
    bg_spatial_features: pd.DataFrame,
) -> pd.DataFrame:
    """Assemble static susceptibility dataset combining positive and background samples.

    Parameters
    ----------
    positives_df : pd.DataFrame
        Phase 3 GSI positive landslide records with terrain features.
    background_df : pd.DataFrame
        Generated background control records with terrain features.
    pos_spatial_features : pd.DataFrame
        Spatial density and proximity features for positive records (computed with self-exclusion).
    bg_spatial_features : pd.DataFrame
        Spatial density and proximity features for background records.

    Returns
    -------
    pd.DataFrame
        Unified static susceptibility dataset.
    """
    pos_combined = positives_df.copy()
    pos_combined["target"] = 1
    pos_combined["sample_type"] = "historical_landslide"

    # Attach spatial context features
    for col in pos_spatial_features.columns:
        pos_combined[col] = pos_spatial_features[col].values

    bg_combined = background_df.copy()
    bg_combined["target"] = 0
    bg_combined["sample_type"] = "background_control"

    for col in bg_spatial_features.columns:
        bg_combined[col] = bg_spatial_features[col].values

    # Concatenate positive and background samples
    full_df = pd.concat([pos_combined, bg_combined], ignore_index=True)

    # Assign Spatial Block IDs for Phase 5 Spatial Cross-Validation
    full_df["spatial_block_id"] = assign_spatial_blocks(full_df, grid_size_deg=0.3)

    # Define standard column ordering
    id_cols = ["slide_id", "sample_type", "target", "state_clean", "district", "spatial_block_id"]
    coord_cols = ["lat_num", "lon_num", "latitude", "longitude"]
    terrain_cols = ["elevation_m", "slope_deg", "dem_covered", "elevation_valid", "slope_valid", "dem_tile"]
    spatial_cols = [
        "nearest_landslide_distance_m",
        "historical_count_1km",
        "historical_count_2km",
        "historical_count_5km",
        "historical_count_10km",
        "unique_historical_count_1km",
        "unique_historical_count_5km",
    ]

    existing_id_cols = [c for c in id_cols if c in full_df.columns]
    existing_coord_cols = [c for c in coord_cols if c in full_df.columns]
    existing_terrain_cols = [c for c in terrain_cols if c in full_df.columns]
    existing_spatial_cols = [c for c in spatial_cols if c in full_df.columns]

    other_cols = [c for c in full_df.columns if c not in set(existing_id_cols + existing_coord_cols + existing_terrain_cols + existing_spatial_cols)]

    final_cols = existing_id_cols + existing_coord_cols + existing_terrain_cols + existing_spatial_cols + other_cols
    full_df = full_df[final_cols]

    # Enforce strict dtype casting for Parquet compatibility
    numeric_float_cols = ["lat_num", "lon_num", "latitude", "longitude", "elevation_m", "slope_deg", "nearest_landslide_distance_m", "min_distance_to_landslide_m"]
    for col in numeric_float_cols:
        if col in full_df.columns:
            full_df[col] = pd.to_numeric(full_df[col], errors="coerce").astype(float)

    numeric_int_cols = ["target", "historical_count_1km", "historical_count_2km", "historical_count_5km", "historical_count_10km", "unique_historical_count_1km", "unique_historical_count_5km"]
    for col in numeric_int_cols:
        if col in full_df.columns:
            full_df[col] = pd.to_numeric(full_df[col], errors="coerce").fillna(0).astype(int)

    # Cast object/string columns to string safely handling non-ASCII/byte strings
    for col in full_df.columns:
        if full_df[col].dtype == "object":
            full_df[col] = full_df[col].apply(
                lambda x: x.decode("utf-8", errors="replace") if isinstance(x, bytes) else str(x) if pd.notna(x) else ""
            )

    return full_df
