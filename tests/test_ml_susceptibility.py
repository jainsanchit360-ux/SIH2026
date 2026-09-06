"""Unit tests for Phase 5 Machine Learning Susceptibility module.

Uses synthetic test fixtures only. Synthetic fixtures are never mixed with
real project data or used for model training.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import joblib

from src.ml.train import (
    PRIMARY_FEATURE_NAMES,
    evaluate_leakage_safe_spatial_cv,
    get_primary_feature_names,
    train_susceptibility_model,
)
from src.ml.evaluate import analyze_threshold_tradeoffs, evaluate_susceptibility_model
from src.ml.explain import explain_susceptibility_prediction, get_feature_importances
from src.ml.predict import classify_prototype_category, predict_susceptibility_score


@pytest.fixture
def synthetic_susceptibility_dataset():
    """Create synthetic susceptibility DataFrame for ML testing."""
    np.random.seed(42)
    n_pos = 50
    n_ctrl = 50
    n_total = n_pos + n_ctrl

    lats = np.random.uniform(24.0, 26.0, n_total)
    lons = np.random.uniform(92.0, 94.0, n_total)
    
    # 5 spatial blocks
    blocks = [f"BLOCK_N{int(lat/0.3):03d}_E{int(lon/0.3):03d}" for lat, lon in zip(lats, lons)]

    df = pd.DataFrame(
        {
            "slide_id": [f"ID_{i:04d}" for i in range(n_total)],
            "sample_type": ["historical_landslide"] * n_pos + ["background_control"] * n_ctrl,
            "target": [1] * n_pos + [0] * n_ctrl,
            "state_clean": ["Assam"] * (n_total // 2) + ["Meghalaya"] * (n_total - n_total // 2),
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


def test_feature_selection_excludes_lat_lon_metadata(synthetic_susceptibility_dataset):
    """Test that get_primary_feature_names excludes raw coordinates and metadata."""
    feature_cols = get_primary_feature_names(synthetic_susceptibility_dataset)

    assert "lat_num" not in feature_cols
    assert "lon_num" not in feature_cols
    assert "latitude" not in feature_cols
    assert "longitude" not in feature_cols
    assert "slide_id" not in feature_cols
    assert "spatial_block_id" not in feature_cols
    assert "target" not in feature_cols

    assert "slope_deg" in feature_cols
    assert "elevation_m" in feature_cols
    assert "nearest_landslide_distance_m" in feature_cols


def test_train_susceptibility_model_all_algorithms(synthetic_susceptibility_dataset):
    """Test training all supported classifiers on synthetic data."""
    feature_cols = get_primary_feature_names(synthetic_susceptibility_dataset)
    X = synthetic_susceptibility_dataset[feature_cols]
    y = synthetic_susceptibility_dataset["target"].values

    for model_type in ["dummy_most_frequent", "random_forest", "gradient_boosting", "hist_gradient_boosting"]:
        model = train_susceptibility_model(X, y, model_type=model_type, random_seed=42)
        assert model is not None
        probs, scores, categories = predict_susceptibility_score(model, X)
        assert len(probs) == len(synthetic_susceptibility_dataset)
        assert np.all((scores >= 0.0) & (scores <= 100.0))


def test_evaluate_leakage_safe_spatial_cv(synthetic_susceptibility_dataset):
    """Test leakage-safe GroupKFold spatial cross-validation pipeline."""
    agg_metrics, fold_metrics, oof_y_true, oof_y_prob = evaluate_leakage_safe_spatial_cv(
        synthetic_susceptibility_dataset,
        model_type="random_forest",
        n_splits=3,
        random_seed=42,
    )

    assert "roc_auc_mean" in agg_metrics
    assert "accuracy_mean" in agg_metrics
    assert len(fold_metrics) == 3
    assert len(oof_y_true) == len(synthetic_susceptibility_dataset)


def test_classify_prototype_category():
    """Test mapping score 0-100 to prototype UI categories."""
    assert classify_prototype_category(15.0) == "LOW"
    assert classify_prototype_category(55.0) == "MODERATE"
    assert classify_prototype_category(85.0) == "HIGH"


def test_explain_susceptibility_prediction(synthetic_susceptibility_dataset):
    """Test prediction explanation narrative generation."""
    feature_cols = get_primary_feature_names(synthetic_susceptibility_dataset)
    X = synthetic_susceptibility_dataset[feature_cols]
    y = synthetic_susceptibility_dataset["target"].values

    model = train_susceptibility_model(X, y, model_type="random_forest", random_seed=42)
    feature_dict = synthetic_susceptibility_dataset.iloc[0].to_dict()

    explanation = explain_susceptibility_prediction(model, feature_cols, feature_dict)

    assert "susceptibility_score" in explanation
    assert "prototype_category" in explanation
    assert "explanation_narrative" in explanation
    assert len(explanation["primary_risk_drivers"]) > 0


def test_model_joblib_save_and_reload(synthetic_susceptibility_dataset, tmp_path):
    """Test model serialization and re-loading with joblib."""
    feature_cols = get_primary_feature_names(synthetic_susceptibility_dataset)
    X = synthetic_susceptibility_dataset[feature_cols]
    y = synthetic_susceptibility_dataset["target"].values

    model = train_susceptibility_model(X, y, model_type="random_forest", random_seed=42)
    save_path = tmp_path / "model.joblib"
    joblib.dump(model, save_path)

    reloaded_model = joblib.load(save_path)
    probs_orig, _, _ = predict_susceptibility_score(model, X)
    probs_reload, _, _ = predict_susceptibility_score(reloaded_model, X)

    assert np.allclose(probs_orig, probs_reload)
