"""Static Landslide Susceptibility ML Model Training Module.

Implements model training pipelines for Dummy baseline, Random Forest, Gradient Boosting,
and HistGradientBoosting classifiers, including leakage-safe spatial GroupKFold cross-validation
where historical density/proximity features are recomputed per fold using training set landslides only.
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.model_selection import GroupKFold, RandomizedSearchCV

from src.config.settings import get_settings
from src.geo.spatial_features import compute_historical_features
from src.ml.evaluate import evaluate_susceptibility_model

logger = logging.getLogger("ml_train")
settings = get_settings()

PRIMARY_FEATURE_NAMES = [
    "elevation_m",
    "slope_deg",
    "nearest_landslide_distance_m",
    "historical_count_1km",
    "historical_count_2km",
    "historical_count_5km",
    "historical_count_10km",
    "unique_historical_count_1km",
    "unique_historical_count_5km",
]

EXCLUDED_METADATA_COLS = [
    "slide_id",
    "sample_type",
    "target",
    "spatial_block_id",
    "state_clean",
    "district",
    "latitude",
    "longitude",
    "lat_num",
    "lon_num",
    "dem_covered",
    "elevation_valid",
    "slope_valid",
    "dem_tile",
    "min_distance_to_landslide_m",
]


def get_primary_feature_names(df: pd.DataFrame) -> List[str]:
    """Return explicit list of primary static predictor features present in DataFrame.

    Excludes raw latitude/longitude coordinates to prevent geographic memorization.

    Parameters
    ----------
    df : pd.DataFrame
        Input susceptibility dataset.

    Returns
    -------
    List[str]
        List of valid static predictor column names.
    """
    return [c for c in PRIMARY_FEATURE_NAMES if c in df.columns]


def train_susceptibility_model(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    model_type: str = "random_forest",
    random_seed: int = 42,
    hyperparams: Optional[Dict[str, Any]] = None,
) -> Any:
    """Train static landslide susceptibility classifier.

    Parameters
    ----------
    X_train : pd.DataFrame
        Training feature matrix.
    y_train : np.ndarray
        Training binary target labels (1=historical landslide, 0=background control).
    model_type : str
        Algorithm choice ('dummy_most_frequent', 'dummy_stratified', 'random_forest',
        'gradient_boosting', 'hist_gradient_boosting').
    random_seed : int
        Random seed for reproducibility.
    hyperparams : Optional[Dict[str, Any]]
        Custom hyperparameter overrides.

    Returns
    -------
    Any
        Fitted Scikit-Learn classifier instance.
    """
    params = hyperparams.copy() if hyperparams else {}

    if model_type == "dummy_most_frequent":
        model = DummyClassifier(strategy="most_frequent")
    elif model_type == "dummy_stratified":
        model = DummyClassifier(strategy="stratified", random_state=random_seed)
    elif model_type == "random_forest":
        default_rf = {
            "n_estimators": 150,
            "max_depth": 12,
            "min_samples_split": 5,
            "min_samples_leaf": 2,
            "max_features": "sqrt",
            "class_weight": "balanced",
            "random_state": random_seed,
            "n_jobs": -1,
        }
        default_rf.update(params)
        model = RandomForestClassifier(**default_rf)
    elif model_type == "gradient_boosting":
        default_gb = {
            "n_estimators": 120,
            "learning_rate": 0.08,
            "max_depth": 6,
            "min_samples_split": 5,
            "min_samples_leaf": 2,
            "subsample": 0.85,
            "random_state": random_seed,
        }
        default_gb.update(params)
        model = GradientBoostingClassifier(**default_gb)
    elif model_type == "hist_gradient_boosting":
        default_hgb = {
            "max_iter": 120,
            "learning_rate": 0.08,
            "max_depth": 8,
            "min_samples_leaf": 5,
            "random_state": random_seed,
        }
        default_hgb.update(params)
        model = HistGradientBoostingClassifier(**default_hgb)
    else:
        raise ValueError(f"Unknown model_type: '{model_type}'")

    model.fit(X_train, y_train)
    return model


def evaluate_leakage_safe_spatial_cv(
    df_full: pd.DataFrame,
    model_type: str = "random_forest",
    n_splits: int = 5,
    random_seed: int = 42,
    threshold: float = 0.50,
    hyperparams: Optional[Dict[str, Any]] = None,
    feature_cols: Optional[List[str]] = None,
    calibrate: bool = False,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], np.ndarray, np.ndarray]:
    """Execute leakage-safe 5-fold spatial GroupKFold cross-validation.

    In every fold, historical density/proximity features are recomputed using ONLY
    the training fold's historical landslide observations as the reference catalogue.

    Parameters
    ----------
    df_full : pd.DataFrame
        Complete Phase 4 dataset containing raw coordinates and spatial_block_id.
    model_type : str
        Classifier type ('random_forest', 'gradient_boosting', etc.).
    n_splits : int
        Number of spatial block folds (default 5).
    random_seed : int
        Random seed.
    threshold : float
        Decision threshold.
    hyperparams : Optional[Dict[str, Any]]
        Hyperparameters.
    feature_cols : Optional[List[str]]
        Explicit feature list for ablation studies.
    calibrate : bool
        If True, apply Platt probability calibration on training fold data.

    Returns
    -------
    Tuple[Dict[str, Any], List[Dict[str, Any]], np.ndarray, np.ndarray]
        (aggregate_metrics, fold_metrics_list, oof_y_true, oof_y_prob)
    """
    gkf = GroupKFold(n_splits=n_splits)
    groups = df_full["spatial_block_id"].values
    
    oof_y_true = np.zeros(len(df_full), dtype=int)
    oof_y_prob = np.zeros(len(df_full), dtype=float)

    fold_metrics_list = []
    if feature_cols is None:
        feature_cols = get_primary_feature_names(df_full)

    logger.info(f"Starting {n_splits}-fold leakage-safe spatial GroupKFold CV for {model_type}...")

    for fold, (train_idx, val_idx) in enumerate(gkf.split(df_full, groups=groups), 1):
        df_train_raw = df_full.iloc[train_idx].copy()
        df_val_raw = df_full.iloc[val_idx].copy()

        # Determine if historical spatial features are required for training/validation
        has_hist_features = any(c not in ["elevation_m", "slope_deg"] for c in feature_cols)

        if has_hist_features:
            # Extract ONLY training historical landslides as reference set for this fold
            ref_landslides_train = df_train_raw[df_train_raw["target"] == 1].copy()

            # 1. Recompute historical features for training fold (self_exclusion=True for positives)
            train_positives = df_train_raw[df_train_raw["target"] == 1]
            train_controls = df_train_raw[df_train_raw["target"] == 0]

            train_pos_feats = compute_historical_features(
                query_df=train_positives,
                reference_landslides_df=ref_landslides_train,
                self_exclusion=True,
                radii_km=[1.0, 2.0, 5.0, 10.0],
            )
            train_ctrl_feats = compute_historical_features(
                query_df=train_controls,
                reference_landslides_df=ref_landslides_train,
                self_exclusion=False,
                radii_km=[1.0, 2.0, 5.0, 10.0],
            )

            for col in train_pos_feats.columns:
                train_positives[col] = train_pos_feats[col].values
                train_controls[col] = train_ctrl_feats[col].values

            df_train_fold = pd.concat([train_positives, train_controls], ignore_index=True)

            # 2. Recompute historical features for validation fold (using ONLY training landslides, self_exclusion=False)
            val_feats = compute_historical_features(
                query_df=df_val_raw,
                reference_landslides_df=ref_landslides_train,
                self_exclusion=False,
                radii_km=[1.0, 2.0, 5.0, 10.0],
            )
            for col in val_feats.columns:
                df_val_raw[col] = val_feats[col].values
        else:
            df_train_fold = df_train_raw

        # 3. Train Model on Leakage-Safe Training Fold
        X_tr = df_train_fold[feature_cols]
        y_tr = df_train_fold["target"].values

        X_v = df_val_raw[feature_cols]
        y_v = df_val_raw["target"].values

        model = train_susceptibility_model(
            X_tr, y_tr, model_type=model_type, random_seed=random_seed + fold, hyperparams=hyperparams
        )

        if calibrate:
            from sklearn.calibration import CalibratedClassifierCV
            calibrator = CalibratedClassifierCV(estimator=model, method="sigmoid", cv=3)
            calibrator.fit(X_tr, y_tr)
            model = calibrator

        # 4. Predict Validation Probabilities
        val_probs = model.predict_proba(X_v)[:, 1]
        val_preds = (val_probs >= threshold).astype(int)

        oof_y_true[val_idx] = y_v
        oof_y_prob[val_idx] = val_probs

        fold_res = evaluate_susceptibility_model(y_v, val_preds, val_probs, threshold=threshold)
        fold_res["fold"] = fold
        fold_res["train_samples"] = len(df_train_fold)
        fold_res["val_samples"] = len(df_val_raw)
        fold_res["unique_val_blocks"] = int(df_val_raw["spatial_block_id"].nunique())
        
        fold_metrics_list.append(fold_res)

    # Compute aggregate metrics across folds
    metrics_to_agg = ["accuracy", "precision", "recall", "f1", "roc_auc", "false_negative_rate", "brier_score"]
    agg_metrics = {}
    for m in metrics_to_agg:
        vals = [f[m] for f in fold_metrics_list]
        agg_metrics[f"{m}_mean"] = float(np.mean(vals))
        agg_metrics[f"{m}_std"] = float(np.std(vals))

    # Out-of-fold global metrics
    oof_res = evaluate_susceptibility_model(oof_y_true, None, oof_y_prob, threshold=threshold)
    agg_metrics["oof_global"] = oof_res

    return agg_metrics, fold_metrics_list, oof_y_true, oof_y_prob
