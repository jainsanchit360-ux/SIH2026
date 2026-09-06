"""Unit tests for spatial feature extraction module.

Uses synthetic test fixtures only. Synthetic fixtures are never mixed with
real project data or used for model training.
"""

import math
import numpy as np
import pandas as pd
import pytest

from src.geo.spatial_features import (
    EARTH_RADIUS_METERS,
    compute_historical_features,
    haversine_distance_meters,
)


def test_haversine_distance_meters():
    """Test Haversine distance calculation in meters."""
    # 1 degree latitude distance along meridian
    dist = haversine_distance_meters(25.0, 92.0, 26.0, 92.0)
    assert pytest.approx(dist, rel=1e-3) == (1.0 / 360.0) * 2.0 * math.pi * EARTH_RADIUS_METERS  # ~111,195m


def test_self_exclusion_nearest_distance():
    """Test self-exclusion logic prevents a point from matching itself at distance 0m."""
    df_ref = pd.DataFrame(
        {
            "lat_num": [25.000, 25.010, 25.100],  # ~1.1km apart
            "lon_num": [92.000, 92.000, 92.000],
        }
    )

    # With self_exclusion=True, nearest distance for point 0 should be point 1 (~1111m)
    res_self = compute_historical_features(df_ref, df_ref, self_exclusion=True, radii_km=[1.0, 2.0, 5.0])
    d0_self = res_self.iloc[0]["nearest_landslide_distance_m"]
    assert pytest.approx(d0_self, rel=1e-2) == 1111.0
    assert d0_self > 10.0  # Must NOT be 0.0m

    # With self_exclusion=False, nearest distance for point 0 is itself (0.0m)
    res_no_self = compute_historical_features(df_ref, df_ref, self_exclusion=False, radii_km=[1.0, 2.0, 5.0])
    d0_no_self = res_no_self.iloc[0]["nearest_landslide_distance_m"]
    assert pytest.approx(d0_no_self, abs=1.0) == 0.0


def test_self_exclusion_density_counts():
    """Test self-exclusion logic subtracts the target point itself from radius counts."""
    # 3 points within 500m of each other
    df_ref = pd.DataFrame(
        {
            "lat_num": [25.000, 25.001, 25.002],
            "lon_num": [92.000, 92.000, 92.000],
        }
    )

    res_self = compute_historical_features(df_ref, df_ref, self_exclusion=True, radii_km=[1.0])
    # Total points in 1km = 3, but with self-exclusion count should be 2 for each point
    assert res_self.iloc[0]["historical_count_1km"] == 2
    assert res_self.iloc[1]["historical_count_1km"] == 2


def test_reference_query_separation():
    """Test feature computation using separate query and reference DataFrames."""
    df_ref = pd.DataFrame(
        {
            "lat_num": [25.000, 25.010],
            "lon_num": [92.000, 92.000],
        }
    )
    df_query = pd.DataFrame(
        {
            "lat_num": [25.005],  # Halfway between ref points (~555m from each)
            "lon_num": [92.000],
        }
    )

    res = compute_historical_features(df_query, df_ref, self_exclusion=False, radii_km=[1.0, 2.0])
    assert len(res) == 1
    assert pytest.approx(res.iloc[0]["nearest_landslide_distance_m"], rel=1e-2) == 555.0
    assert res.iloc[0]["historical_count_1km"] == 2
