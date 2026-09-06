"""Unit tests for Phase 5B Static Susceptibility Model Robustness module.

Tests probability distribution statistics, extended threshold sweep, feature ablation,
and spatial GroupKFold CV extensions.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.ml.evaluate import (
    analyze_threshold_tradeoffs,
    compute_probability_distribution_stats,
    evaluate_susceptibility_model,
)
from src.ml.train import (
    evaluate_leakage_safe_spatial_cv,
    get_primary_feature_names,
)


@pytest.fixture
def synthetic_spatial_dataset():
    """Create synthetic spatial dataset with 4 spatial blocks."""
    np.random.seed(42)
    n_pos = 40
    n_ctrl = 40
    n_total = n_pos + n_ctrl

    lats = np.random.uniform(24.0, 26.0, n_total)
    lons = np.random.uniform(92.0, 94.0, n_total)
    
    # 4 spatial blocks
    blocks = [f"BLOCK_{i % 4}" for i in range(n_total)]

    df = pd.DataFrame(
        {
            "slide_id": [f"ID_{i:04d}" for i in range(n_total)],
            "sample_type": ["historical_landslide"] * n_pos + ["background_control"] * n_ctrl,
            "target": [1] * n_pos + [0] * n_ctrl,
            "state_clean": ["Assam"] * n_total,
            "district": ["Region"] * n_total,
            "lat_num": lats,
            "lon_num": lons,
            "latitude": lats,
            "longitude": lons,
            "elevation_m": np.random.uniform(100, 1500, n_total),
            "slope_deg": np.random.uniform(5, 45, n_total),
            "nearest_landslide_distance_m": np.random.uniform(100, 10000, n_total),
            "historical_count_1km": np.random.randint(0, 5, n_total),
            "historical_count_2km": np.random.randint(0, 10, n_total),
            "historical_count_5km": np.random.randint(0, 20, n_total),
            "historical_count_10km": np.random.randint(0, 40, n_total),
            "unique_historical_count_1km": np.random.randint(0, 3, n_total),
            "unique_historical_count_5km": np.random.randint(0, 10, n_total),
            "spatial_block_id": blocks,
        }
    )

    return df


def test_probability_distribution_stats():
    """Test probability summary statistics computation."""
    y_true = np.array([1, 1, 1, 0, 0, 0])
    y_prob = np.array([0.9, 0.8, 0.7, 0.2, 0.3, 0.1])

    stats = compute_probability_distribution_stats(y_true, y_prob)

    assert "positives" in stats
    assert "controls" in stats
    assert stats["positives"]["median"] == 0.8
    assert stats["controls"]["median"] == 0.2
    assert stats["positives"]["count"] == 3
    assert stats["controls"]["count"] == 3


def test_extended_threshold_tradeoffs():
    """Test extended threshold sweep dataframe output."""
    y_true = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    y_prob = np.array([0.85, 0.65, 0.45, 0.25, 0.15, 0.10, 0.05, 0.02])

    thresholds = [0.05, 0.10, 0.20, 0.30, 0.50]
    th_df = analyze_threshold_tradeoffs(y_true, y_prob, thresholds=thresholds)

    assert len(th_df) == len(thresholds)
    assert "specificity" in th_df.columns
    assert "false_negative_rate" in th_df.columns
    assert "false_positive_rate" in th_df.columns
    assert th_df.iloc[0]["recall"] >= th_df.iloc[-1]["recall"]


def test_ablation_spatial_cv_subsets(synthetic_spatial_dataset):
    """Test evaluate_leakage_safe_spatial_cv with explicit feature subsets."""
    terrain_features = ["elevation_m", "slope_deg"]
    
    agg_metrics, fold_metrics, oof_y_true, oof_y_prob = evaluate_leakage_safe_spatial_cv(
        synthetic_spatial_dataset,
        model_type="random_forest",
        n_splits=3,
        random_seed=42,
        feature_cols=terrain_features,
    )

    assert "roc_auc_mean" in agg_metrics
    assert len(fold_metrics) == 3
    assert len(oof_y_prob) == len(synthetic_spatial_dataset)


def test_spatial_cv_calibration_option(synthetic_spatial_dataset):
    """Test evaluate_leakage_safe_spatial_cv with Platt calibration enabled."""
    agg_metrics, fold_metrics, oof_y_true, oof_y_prob = evaluate_leakage_safe_spatial_cv(
        synthetic_spatial_dataset,
        model_type="random_forest",
        n_splits=3,
        random_seed=42,
        calibrate=True,
    )

    assert "brier_score_mean" in agg_metrics
    assert np.all((oof_y_prob >= 0.0) & (oof_y_prob <= 1.0))
