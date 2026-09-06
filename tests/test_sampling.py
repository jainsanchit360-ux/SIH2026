"""Unit tests for background control sampling module.

Uses synthetic fixtures only. Synthetic fixtures are never mixed with
real project data or used for model training.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.data.loaders.dem_loader import SRTMTileIndex, parse_tile_bounds
from src.geo.sampling import derive_ner_state_bounds, generate_background_samples
from src.geo.spatial_features import haversine_distance_meters


@pytest.fixture
def synthetic_gsi_and_dem(tmp_path):
    """Create synthetic GSI DataFrame and mock SRTMTileIndex."""
    # Synthetic positive landslides in Assam (24.0-25.0 N, 92.0-93.0 E)
    gsi_data = {
        "slide_id": ["AS_01", "AS_02", "AS_03"],
        "state_clean": ["Assam", "Assam", "Assam"],
        "lat_num": [24.25, 24.50, 24.75],
        "lon_num": [92.25, 92.50, 92.75],
    }
    df_gsi = pd.DataFrame(gsi_data)

    # Create synthetic HGT raster file (3601 x 3601 int16 = 500m elevation)
    hgt_file = tmp_path / "N24E092.hgt"
    data = np.full((3601, 3601), 500, dtype=">i2")
    data.tofile(hgt_file)

    info = parse_tile_bounds("N24E092.hgt")
    tile_index = SRTMTileIndex()
    tile_index.add_tile(info, hgt_file)

    return df_gsi, tile_index


def test_derive_ner_state_bounds(synthetic_gsi_and_dem):
    """Test state bounding box derivation."""
    df_gsi, _ = synthetic_gsi_and_dem
    bounds = derive_ner_state_bounds(df_gsi, buffer_deg=0.05)

    assert "Assam" in bounds
    min_lat, max_lat, min_lon, max_lon = bounds["Assam"]
    assert min_lat <= 24.25 and max_lat >= 24.75
    assert min_lon <= 92.25 and max_lon >= 92.75


def test_generate_background_samples_exclusion_buffer(synthetic_gsi_and_dem):
    """Test background sample generation enforces 500m exclusion buffer from positives."""
    df_gsi, tile_index = synthetic_gsi_and_dem
    exclusion_m = 500.0

    df_bg, audit = generate_background_samples(
        df_gsi,
        tile_index,
        target_ratio=2.0,  # Request 6 controls for 3 positives
        exclusion_distance_m=exclusion_m,
        random_seed=42,
    )

    assert len(df_bg) > 0
    assert audit["exclusion_distance_m"] == exclusion_m

    # Verify every control point is >= 500m from all positive landslides
    for _, bg_row in df_bg.iterrows():
        bg_lat = bg_row["lat_num"]
        bg_lon = bg_row["lon_num"]

        for _, pos_row in df_gsi.iterrows():
            pos_lat = pos_row["lat_num"]
            pos_lon = pos_row["lon_num"]
            dist_m = haversine_distance_meters(bg_lat, bg_lon, pos_lat, pos_lon)
            assert dist_m >= exclusion_m


def test_generate_background_samples_reproducibility(synthetic_gsi_and_dem):
    """Test random seed reproducibility."""
    df_gsi, tile_index = synthetic_gsi_and_dem

    df_bg1, _ = generate_background_samples(df_gsi, tile_index, random_seed=123)
    df_bg2, _ = generate_background_samples(df_gsi, tile_index, random_seed=123)

    assert len(df_bg1) == len(df_bg2)
    assert np.allclose(df_bg1["lat_num"], df_bg2["lat_num"])
    assert np.allclose(df_bg1["lon_num"], df_bg2["lon_num"])
