"""Unit tests for static feature engineering and dataset assembly module.

Uses synthetic test fixtures only. Synthetic fixtures are never mixed with
real project data or used for model training.
"""

import numpy as np
import pandas as pd
import pytest

from src.features.static_features import (
    assemble_susceptibility_dataset,
    assign_spatial_blocks,
)


def test_assign_spatial_blocks():
    """Test geographic spatial block ID assignment for spatial CV."""
    df = pd.DataFrame(
        {
            "lat_num": [25.10, 25.15, 26.50],
            "lon_num": [92.10, 92.15, 93.80],
        }
    )

    block_ids = assign_spatial_blocks(df, grid_size_deg=0.3)
    assert len(block_ids) == 3
    # 25.10 / 0.3 = 83.66 -> floor = 83, 92.10 / 0.3 = 307.0 -> floor = 307
    assert block_ids.iloc[0] == "BLOCK_N083_E307"
    assert block_ids.iloc[1] == "BLOCK_N083_E307"  # Same ~30km grid block
    assert block_ids.iloc[2] != block_ids.iloc[0]   # Different grid block


def test_assemble_susceptibility_dataset():
    """Test merging positive and background samples into static susceptibility dataset."""
    positives_df = pd.DataFrame(
        {
            "slide_id": ["POS_01", "POS_02"],
            "state_clean": ["Assam", "Assam"],
            "district": ["Cachar", "Cachar"],
            "lat_num": [24.8, 24.9],
            "lon_num": [92.8, 92.9],
            "latitude": [24.8, 24.9],
            "longitude": [92.8, 92.9],
            "elevation_m": [450.0, 520.0],
            "slope_deg": [25.0, 31.0],
            "dem_covered": [True, True],
            "elevation_valid": [True, True],
            "slope_valid": [True, True],
            "dem_tile": ["N24E092", "N24E092"],
        }
    )

    background_df = pd.DataFrame(
        {
            "slide_id": ["CTRL_AS_00001", "CTRL_AS_00002"],
            "state_clean": ["Assam", "Assam"],
            "district": ["Assam Region", "Assam Region"],
            "lat_num": [24.1, 24.2],
            "lon_num": [92.1, 92.2],
            "latitude": [24.1, 24.2],
            "longitude": [92.1, 92.2],
            "elevation_m": [150.0, 200.0],
            "slope_deg": [5.0, 8.0],
            "dem_covered": [True, True],
            "elevation_valid": [True, True],
            "slope_valid": [True, True],
            "dem_tile": ["N24E092", "N24E092"],
        }
    )

    pos_spatial_features = pd.DataFrame(
        {
            "nearest_landslide_distance_m": [1200.0, 1200.0],
            "historical_count_1km": [0, 0],
            "historical_count_2km": [1, 1],
            "historical_count_5km": [1, 1],
            "historical_count_10km": [1, 1],
            "unique_historical_count_1km": [0, 0],
            "unique_historical_count_5km": [1, 1],
        }
    )

    bg_spatial_features = pd.DataFrame(
        {
            "nearest_landslide_distance_m": [15000.0, 18000.0],
            "historical_count_1km": [0, 0],
            "historical_count_2km": [0, 0],
            "historical_count_5km": [0, 0],
            "historical_count_10km": [0, 0],
            "unique_historical_count_1km": [0, 0],
            "unique_historical_count_5km": [0, 0],
        }
    )

    full_df = assemble_susceptibility_dataset(
        positives_df, background_df, pos_spatial_features, bg_spatial_features
    )

    assert len(full_df) == 4
    assert (full_df["target"] == [1, 1, 0, 0]).all()
    assert "spatial_block_id" in full_df.columns
    assert "nearest_landslide_distance_m" in full_df.columns
    assert full_df["sample_type"].iloc[0] == "historical_landslide"
    assert full_df["sample_type"].iloc[2] == "background_control"
