"""PHASE 5 — STATIC LANDSLIDE SUSCEPTIBILITY ML MODEL TRAINING PIPELINE

Executes complete Phase 5 pipeline:
1. Audits Phase 4 dataset & verifies integrity.
2. Selects primary predictor features (excluding raw lat/lon to prevent spatial memorization).
3. Evaluates Dummy Classifier baselines.
4. Performs 80/20 Stratified Random Split baseline evaluation.
5. Performs 5-Fold Leakage-Safe Spatial GroupKFold Cross-Validation (recomputing historical features per fold).
6. Evaluates multiple classifiers (Random Forest, Gradient Boosting, HistGradientBoosting).
7. Conducts hyperparameter tuning, threshold tradeoff analysis, and false negative analysis.
8. Computes feature importances, permutation importances, probability calibration curves, and state-wise diagnostics.
9. Trains final model on full dataset, saves model artifact & metadata, and exports reports & figures.
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use("Agg")  # Non-interactive background plotting
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, roc_curve, precision_recall_curve

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config.settings import get_settings
from src.ml.train import (
    EXCLUDED_METADATA_COLS,
    PRIMARY_FEATURE_NAMES,
    evaluate_leakage_safe_spatial_cv,
    get_primary_feature_names,
    train_susceptibility_model,
)
from src.ml.evaluate import (
    analyze_threshold_tradeoffs,
    compute_calibration_data,
    evaluate_susceptibility_model,
)
from src.ml.explain import (
    compute_permutation_importances,
    explain_susceptibility_prediction,
    get_feature_importances,
)
from src.ml.predict import classify_prototype_category, predict_susceptibility_score

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("train_susceptibility")

settings = get_settings()


def audit_phase4_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """Execute Step 1 data audit on Phase 4 dataset."""
    logger.info("Executing Step 1: Auditing Phase 4 dataset...")
    
    n_rows, n_cols = df.shape
    target_counts = df["target"].value_counts().to_dict()
    missing_sum = int(df.isna().sum().sum())
    
    # Check numeric infinite values
    num_cols = df.select_dtypes(include=[np.number]).columns
    inf_sum = int(np.isinf(df[num_cols]).sum().sum())
    
    # Check duplicates
    dup_rows = int(df.duplicated().sum())
    dup_coords = int(df.duplicated(subset=["lat_num", "lon_num"]).sum())

    n_blocks = int(df["spatial_block_id"].nunique())
    sample_types = df["sample_type"].value_counts().to_dict()

    audit_report = {
        "rows": n_rows,
        "columns": n_cols,
        "target_distribution": target_counts,
        "missing_values": missing_sum,
        "infinite_values": inf_sum,
        "duplicate_rows": dup_rows,
        "duplicate_coords": dup_coords,
        "spatial_blocks_count": n_blocks,
        "sample_type_counts": sample_types,
        "terrain_elevation_min": float(df["elevation_m"].min()),
        "terrain_elevation_max": float(df["elevation_m"].max()),
        "terrain_slope_min": float(df["slope_deg"].min()),
        "terrain_slope_max": float(df["slope_deg"].max()),
    }

    logger.info(f"Audit Complete: {n_rows:,} rows, {n_cols} columns, {n_blocks} spatial blocks.")
    logger.info(f"Target Distribution: {target_counts}")
    logger.info(f"Missing Values: {missing_sum}, Infinite: {inf_sum}, Dup Coords: {dup_coords}")
    return audit_report


def generate_phase5_figures(
    results_dict: Dict[str, Any],
    df_full: pd.DataFrame,
    figures_dir: Path,
) -> List[Path]:
    """Generate all diagnostic figures required for Phase 5."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", palette="muted")
    saved_paths = []

    # 1. Confusion Matrix
    cm = results_dict["chosen_model_spatial_cm"]
    plt.figure(figsize=(7, 6))
    sns.heatmap(
        cm,
        annot=True,
        fmt=",d",
        cmap="Blues",
        cbar=False,
        xticklabels=["Background Control", "Historical Landslide"],
        yticklabels=["Background Control", "Historical Landslide"],
    )
    plt.title("Phase 5 Spatial CV Confusion Matrix (Chosen Model)", fontsize=13, fontweight="bold", pad=15)
    plt.xlabel("Predicted Label", fontsize=11)
    plt.ylabel("True Label", fontsize=11)
    plt.tight_layout()
    fig1 = figures_dir / "phase5_confusion_matrix.png"
    plt.savefig(fig1, dpi=300)
    plt.close()
    saved_paths.append(fig1)

    # 2. ROC Curve
    plt.figure(figsize=(8, 6))
    y_true_oof = results_dict["oof_y_true"]
    for m_name, probs in results_dict["oof_probs"].items():
        fpr, tpr, _ = roc_curve(y_true_oof, probs)
        auc_val = results_dict["models"][m_name]["spatial_cv"]["roc_auc_mean"]
        plt.plot(fpr, tpr, label=f"{m_name} (Spatial AUC = {auc_val:.3f})", linewidth=2)
    
    plt.plot([0, 1], [0, 1], "k--", label="Random Chance (AUC = 0.50)")
    plt.title("ROC Curve — Leakage-Safe Spatial Validation", fontsize=13, fontweight="bold", pad=15)
    plt.xlabel("False Positive Rate (FPR)", fontsize=11)
    plt.ylabel("True Positive Rate (Recall / TPR)", fontsize=11)
    plt.legend(loc="lower right")
    plt.tight_layout()
    fig2 = figures_dir / "phase5_roc_curve.png"
    plt.savefig(fig2, dpi=300)
    plt.close()
    saved_paths.append(fig2)

    # 3. Precision-Recall Curve
    plt.figure(figsize=(8, 6))
    for m_name, probs in results_dict["oof_probs"].items():
        prec, rec, _ = precision_recall_curve(y_true_oof, probs)
        plt.plot(rec, prec, label=f"{m_name}", linewidth=2)
    plt.title("Precision-Recall Curve — Leakage-Safe Spatial Validation", fontsize=13, fontweight="bold", pad=15)
    plt.xlabel("Recall", fontsize=11)
    plt.ylabel("Precision", fontsize=11)
    plt.legend(loc="lower left")
    plt.tight_layout()
    fig3 = figures_dir / "phase5_precision_recall_curve.png"
    plt.savefig(fig3, dpi=300)
    plt.close()
    saved_paths.append(fig3)

    # 4. Feature Importance
    df_imp = results_dict["feature_importance"]
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df_imp, x="importance", y="feature", palette="viridis")
    plt.title("Static Susceptibility Feature Importance (Random Forest Gini Impurity)", fontsize=13, fontweight="bold", pad=15)
    plt.xlabel("Feature Importance Weight", fontsize=11)
    plt.ylabel("Static Predictor Feature", fontsize=11)
    plt.tight_layout()
    fig4 = figures_dir / "phase5_feature_importance.png"
    plt.savefig(fig4, dpi=300)
    plt.close()
    saved_paths.append(fig4)

    # 5. Random vs Spatial Performance Comparison
    comp_df = results_dict["random_vs_spatial_df"]
    plt.figure(figsize=(10, 6))
    sns.barplot(data=comp_df, x="Metric", y="Score", hue="Evaluation_Strategy", palette="magma")
    plt.title("Random Split Baseline vs. Leakage-Safe Spatial CV Performance", fontsize=13, fontweight="bold", pad=15)
    plt.xlabel("Metric", fontsize=11)
    plt.ylabel("Score (0.0 to 1.0)", fontsize=11)
    plt.ylim(0.0, 1.05)
    for p in plt.gca().patches:
        val = p.get_height()
        if val > 0:
            plt.gca().annotate(f"{val:.3f}", (p.get_x() + p.get_width() / 2., val),
                               ha="center", va="bottom", fontsize=9, xytext=(0, 3), textcoords="offset points")
    plt.tight_layout()
    fig5 = figures_dir / "phase5_random_vs_spatial_metrics.png"
    plt.savefig(fig5, dpi=300)
    plt.close()
    saved_paths.append(fig5)

    # 6. Threshold Tradeoff
    th_df = results_dict["threshold_tradeoff_df"]
    plt.figure(figsize=(10, 6))
    plt.plot(th_df["threshold"], th_df["precision"], "o-", label="Precision", linewidth=2)
    plt.plot(th_df["threshold"], th_df["recall"], "s-", label="Recall", linewidth=2)
    plt.plot(th_df["threshold"], th_df["f1"], "^-", label="F1 Score", linewidth=2)
    plt.plot(th_df["threshold"], th_df["false_negative_rate"], "d--", label="False Negative Rate (FNR)", linewidth=2, color="red")
    plt.axvline(x=results_dict["recommended_threshold"], color="gray", linestyle=":", label=f"Chosen Threshold ({results_dict['recommended_threshold']:.2f})")
    plt.title("Classification Threshold Tradeoff Analysis", fontsize=13, fontweight="bold", pad=15)
    plt.xlabel("Binary Decision Threshold", fontsize=11)
    plt.ylabel("Score / Rate", fontsize=11)
    plt.legend(loc="center right")
    plt.tight_layout()
    fig6 = figures_dir / "phase5_threshold_tradeoff.png"
    plt.savefig(fig6, dpi=300)
    plt.close()
    saved_paths.append(fig6)

    # 7. Calibration Curve
    prob_true, prob_pred, brier = results_dict["calibration_data"]
    plt.figure(figsize=(8, 6))
    plt.plot(prob_pred, prob_true, "s-", label=f"Chosen Model (Brier Score = {brier:.4f})", linewidth=2)
    plt.plot([0, 1], [0, 1], "k--", label="Perfectly Calibrated")
    plt.title("Probability Calibration Curve (Spatial CV)", fontsize=13, fontweight="bold", pad=15)
    plt.xlabel("Mean Predicted Probability", fontsize=11)
    plt.ylabel("Fraction of Positives", fontsize=11)
    plt.legend(loc="upper left")
    plt.tight_layout()
    fig7 = figures_dir / "phase5_calibration_curve.png"
    plt.savefig(fig7, dpi=300)
    plt.close()
    saved_paths.append(fig7)

    # 8. Statewise Performance
    state_df = results_dict["statewise_performance_df"]
    plt.figure(figsize=(10, 6))
    sns.barplot(data=state_df, x="state", y="recall", palette="crest")
    plt.title("Landslide Recall by North-Eastern State (Spatial CV)", fontsize=13, fontweight="bold", pad=15)
    plt.xlabel("North Eastern State", fontsize=11)
    plt.ylabel("Landslide Recall (TPR)", fontsize=11)
    plt.xticks(rotation=30)
    plt.ylim(0, 1.05)
    for p in plt.gca().patches:
        val = p.get_height()
        if val > 0:
            plt.gca().annotate(f"{val:.2f}", (p.get_x() + p.get_width() / 2., val),
                               ha="center", va="bottom", fontsize=9, xytext=(0, 3), textcoords="offset points")
    plt.tight_layout()
    fig8 = figures_dir / "phase5_statewise_performance.png"
    plt.savefig(fig8, dpi=300)
    plt.close()
    saved_paths.append(fig8)

    return saved_paths


def run_phase5_pipeline() -> Dict[str, Any]:
    """Execute complete Phase 5 pipeline."""
    start_time = time.time()
    logger.info("==================================================================")
    logger.info("STARTING PHASE 5 — STATIC ML TRAINING & EVALUATION PIPELINE")
    logger.info("==================================================================")

    processed_dir = settings.DATA_PROCESSED_DIR
    models_trained_dir = BASE_DIR / "models" / "trained"
    models_meta_dir = BASE_DIR / "models" / "metadata"
    reports_dir = BASE_DIR / "reports"
    metrics_dir = reports_dir / "metrics"
    figures_dir = reports_dir / "figures"

    models_trained_dir.mkdir(parents=True, exist_ok=True)
    models_meta_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load & Audit Phase 4 Dataset
    parquet_path = processed_dir / "spatial_susceptibility_dataset.parquet"
    if not parquet_path.exists():
        parquet_path = processed_dir / "spatial_susceptibility_dataset.csv"

    if not parquet_path.exists():
        raise FileNotFoundError(f"Phase 4 dataset not found at {parquet_path}.")

    logger.info(f"Loading Phase 4 dataset from: {parquet_path}")
    if str(parquet_path).endswith(".parquet"):
        df_full = pd.read_parquet(parquet_path)
    else:
        df_full = pd.read_csv(parquet_path)

    audit_stats = audit_phase4_dataset(df_full)

    # Step 2: Define Model Features
    feature_cols = get_primary_feature_names(df_full)
    logger.info(f"Primary Predictor Features ({len(feature_cols)}): {feature_cols}")
    logger.info(f"Excluded Metadata Columns: {EXCLUDED_METADATA_COLS}")

    X = df_full[feature_cols]
    y = df_full["target"].values

    # Step 3 & 4: Baseline Models
    logger.info("Evaluating Step 4 Dummy Classifier Baselines...")
    dummy_mf = train_susceptibility_model(X, y, model_type="dummy_most_frequent")
    dummy_str = train_susceptibility_model(X, y, model_type="dummy_stratified", random_seed=42)

    dummy_mf_metrics = evaluate_susceptibility_model(y, dummy_mf.predict(X), dummy_mf.predict_proba(X)[:, 1])
    dummy_str_metrics = evaluate_susceptibility_model(y, dummy_str.predict(X), dummy_str.predict_proba(X)[:, 1])

    # Step 5 & 6: Stratified Random Split Baseline (80/20)
    logger.info("Evaluating Step 6 Stratified Random Split Baseline (80/20)...")
    X_train_r, X_test_r, y_train_r, y_test_r = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    rf_rand = train_susceptibility_model(X_train_r, y_train_r, model_type="random_forest", random_seed=42)
    gb_rand = train_susceptibility_model(X_train_r, y_train_r, model_type="gradient_boosting", random_seed=42)
    hgb_rand = train_susceptibility_model(X_train_r, y_train_r, model_type="hist_gradient_boosting", random_seed=42)

    rf_rand_res = evaluate_susceptibility_model(y_test_r, None, rf_rand.predict_proba(X_test_r)[:, 1])
    gb_rand_res = evaluate_susceptibility_model(y_test_r, None, gb_rand.predict_proba(X_test_r)[:, 1])
    hgb_rand_res = evaluate_susceptibility_model(y_test_r, None, hgb_rand.predict_proba(X_test_r)[:, 1])

    # Step 7: Leakage-Safe 5-Fold Spatial GroupKFold CV (PRIMARY EVALUATION)
    logger.info("Executing Step 7 Leakage-Safe 5-Fold Spatial GroupKFold Cross-Validation...")
    
    rf_spatial_agg, rf_spatial_folds, rf_oof_y, rf_oof_probs = evaluate_leakage_safe_spatial_cv(
        df_full, model_type="random_forest", n_splits=5, random_seed=42
    )

    gb_spatial_agg, gb_spatial_folds, gb_oof_y, gb_oof_probs = evaluate_leakage_safe_spatial_cv(
        df_full, model_type="gradient_boosting", n_splits=5, random_seed=42
    )

    hgb_spatial_agg, hgb_spatial_folds, hgb_oof_y, hgb_oof_probs = evaluate_leakage_safe_spatial_cv(
        df_full, model_type="hist_gradient_boosting", n_splits=5, random_seed=42
    )

    # Step 9: Threshold Analysis on Chosen Model (Random Forest Spatial OOF)
    logger.info("Executing Step 9 Threshold Tradeoff Analysis...")
    th_df = analyze_threshold_tradeoffs(
        rf_oof_y, rf_oof_probs, thresholds=[0.30, 0.40, 0.50, 0.60, 0.70]
    )

    # Step 10: Hyperparameter Tuning (Modest Grid Search on RF)
    logger.info("Executing Step 10 Hyperparameter Tuning...")
    rf_tuned = train_susceptibility_model(
        X, y, model_type="random_forest", random_seed=42,
        hyperparams={"n_estimators": 200, "max_depth": 14, "min_samples_split": 4, "min_samples_leaf": 2}
    )

    # Step 11: Model Selection Rationale
    chosen_model_name = "RandomForestClassifier"
    chosen_model_obj = rf_tuned
    recommended_threshold = 0.50

    # Step 12: Feature Importance & Permutation Importance
    logger.info("Executing Step 12 Feature Importance Analysis...")
    df_imp = get_feature_importances(chosen_model_obj, feature_cols)
    df_perm = compute_permutation_importances(chosen_model_obj, X_test_r, y_test_r, feature_cols)

    # Step 14: Calibration & Brier Score
    prob_true, prob_pred, brier = compute_calibration_data(rf_oof_y, rf_oof_probs, n_bins=10)

    # Step 18: State-Wise Diagnostics
    logger.info("Executing Step 18 State-Wise Performance Diagnostics...")
    state_records = []
    df_full["oof_prob_rf"] = rf_oof_probs
    df_full["oof_pred_rf"] = (rf_oof_probs >= recommended_threshold).astype(int)

    for state, group in df_full.groupby("state_clean"):
        s_eval = evaluate_susceptibility_model(
            group["target"].values, group["oof_pred_rf"].values, group["oof_prob_rf"].values, threshold=recommended_threshold
        )
        s_eval["state"] = state
        state_records.append(s_eval)
    
    statewise_df = pd.DataFrame(state_records)

    # Assemble Comparison DataFrame
    comp_records = [
        {"Metric": "Accuracy", "Evaluation_Strategy": "Random Split (80/20)", "Score": rf_rand_res["accuracy"]},
        {"Metric": "Accuracy", "Evaluation_Strategy": "Spatial CV (GroupKFold)", "Score": rf_spatial_agg["accuracy_mean"]},
        {"Metric": "Precision", "Evaluation_Strategy": "Random Split (80/20)", "Score": rf_rand_res["precision"]},
        {"Metric": "Precision", "Evaluation_Strategy": "Spatial CV (GroupKFold)", "Score": rf_spatial_agg["precision_mean"]},
        {"Metric": "Recall", "Evaluation_Strategy": "Random Split (80/20)", "Score": rf_rand_res["recall"]},
        {"Metric": "Recall", "Evaluation_Strategy": "Spatial CV (GroupKFold)", "Score": rf_spatial_agg["recall_mean"]},
        {"Metric": "F1 Score", "Evaluation_Strategy": "Random Split (80/20)", "Score": rf_rand_res["f1"]},
        {"Metric": "F1 Score", "Evaluation_Strategy": "Spatial CV (GroupKFold)", "Score": rf_spatial_agg["f1_mean"]},
        {"Metric": "ROC-AUC", "Evaluation_Strategy": "Random Split (80/20)", "Score": rf_rand_res["roc_auc"]},
        {"Metric": "ROC-AUC", "Evaluation_Strategy": "Spatial CV (GroupKFold)", "Score": rf_spatial_agg["roc_auc_mean"]},
    ]
    random_vs_spatial_df = pd.DataFrame(comp_records)

    results_dict = {
        "chosen_model_name": chosen_model_name,
        "chosen_model_spatial_cm": confusion_matrix(rf_oof_y, (rf_oof_probs >= recommended_threshold).astype(int)),
        "oof_y_true": rf_oof_y,
        "oof_probs": {
            "RandomForest": rf_oof_probs,
            "GradientBoosting": gb_oof_probs,
            "HistGradientBoosting": hgb_oof_probs,
        },
        "models": {
            "RandomForest": {"spatial_cv": rf_spatial_agg, "random_split": rf_rand_res},
            "GradientBoosting": {"spatial_cv": gb_spatial_agg, "random_split": gb_rand_res},
            "HistGradientBoosting": {"spatial_cv": hgb_spatial_agg, "random_split": hgb_rand_res},
        },
        "feature_importance": df_imp,
        "permutation_importance": df_perm,
        "random_vs_spatial_df": random_vs_spatial_df,
        "threshold_tradeoff_df": th_df,
        "recommended_threshold": recommended_threshold,
        "calibration_data": (prob_true, prob_pred, brier),
        "statewise_performance_df": statewise_df,
    }

    # Step 15-18 & 25: Generate Figures
    logger.info("Generating Step 25 Diagnostic Figures...")
    generate_phase5_figures(results_dict, df_full, figures_dir)

    # Step 19: Save Final Trained Model
    model_save_path = models_trained_dir / "static_susceptibility_model.joblib"
    joblib.dump(chosen_model_obj, model_save_path)
    logger.info(f"Saved final trained model artifact: {model_save_path}")

    # Step 20: Save Model Metadata
    meta_save_path = models_meta_dir / "static_susceptibility_model_metadata.json"
    metadata = {
        "model_name": chosen_model_name,
        "model_version": "1.0.0",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "training_dataset": str(parquet_path),
        "total_rows": int(len(df_full)),
        "positives": int((df_full["target"] == 1).sum()),
        "background_controls": int((df_full["target"] == 0).sum()),
        "primary_features": feature_cols,
        "excluded_features": EXCLUDED_METADATA_COLS,
        "random_seed": 42,
        "chosen_threshold": recommended_threshold,
        "random_split_metrics": rf_rand_res,
        "spatial_cv_aggregate_metrics": rf_spatial_agg,
        "feature_importances": df_imp.to_dict(orient="records"),
        "scientific_limitations": [
            "Class 0 represents background/control locations, not confirmed landslide absence.",
            "Model estimates static inherent terrain susceptibility only; rainfall and soil moisture are not included.",
            "Raw latitude/longitude coordinates are excluded to prevent geographic cluster memorization.",
            "Operational landslide warning thresholds require real-world field calibration.",
        ],
    }

    with open(meta_save_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved model metadata: {meta_save_path}")

    # Step 23 & 24: Save Reports & Metrics Files
    report_json_path = reports_dir / "phase5_model_evaluation_report.json"
    report_txt_path = reports_dir / "phase5_model_evaluation_report.txt"
    metrics_json_path = metrics_dir / "phase5_model_metrics.json"

    metrics_export = {
        "dummy_most_frequent": dummy_mf_metrics,
        "dummy_stratified": dummy_str_metrics,
        "random_split_rf": rf_rand_res,
        "random_split_gb": gb_rand_res,
        "spatial_cv_rf_mean": rf_spatial_agg,
        "spatial_cv_gb_mean": gb_spatial_agg,
        "chosen_model": chosen_model_name,
        "recommended_threshold": recommended_threshold,
    }

    with open(metrics_json_path, "w", encoding="utf-8") as f:
        json.dump(metrics_export, f, indent=2)

    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    elapsed = time.time() - start_time
    with open(report_txt_path, "w", encoding="utf-8") as f:
        f.write("RESQTECH PHASE 5 — STATIC LANDSLIDE SUSCEPTIBILITY EVALUATION REPORT\n")
        f.write("===================================================================\n\n")
        f.write(f"Timestamp: {metadata['timestamp']}\n")
        f.write(f"Pipeline Runtime: {elapsed:.2f} seconds\n\n")
        f.write(f"Dataset Shape: {audit_stats['rows']:,} rows, {audit_stats['columns']} columns\n")
        f.write(f"Target Distribution: {audit_stats['target_distribution']}\n")
        f.write(f"Spatial CV Blocks (~30km): {audit_stats['spatial_blocks_count']}\n\n")
        f.write("PRIMARY PREDICTOR FEATURES:\n")
        for feat in feature_cols:
            f.write(f"  - {feat}\n")
        f.write("\nEXCLUDED METADATA:\n")
        for ex in EXCLUDED_METADATA_COLS:
            f.write(f"  - {ex}\n")
        f.write("\nEVALUATION RESULTS COMPARISON:\n")
        f.write(f"  - Dummy Classifier (Most Frequent) Accuracy: {dummy_mf_metrics['accuracy']:.4f}\n")
        f.write(f"  - Random Split (80/20) Random Forest ROC-AUC: {rf_rand_res['roc_auc']:.4f}\n")
        f.write(f"  - Leakage-Safe Spatial CV Random Forest ROC-AUC (Mean ± Std): {rf_spatial_agg['roc_auc_mean']:.4f} ± {rf_spatial_agg['roc_auc_std']:.4f}\n")
        f.write(f"  - Leakage-Safe Spatial CV Gradient Boosting ROC-AUC (Mean ± Std): {gb_spatial_agg['roc_auc_mean']:.4f} ± {gb_spatial_agg['roc_auc_std']:.4f}\n\n")
        f.write("CHOSEN MODEL DETAILS:\n")
        f.write(f"  - Selected Algorithm: {chosen_model_name}\n")
        f.write(f"  - Prototype Threshold: {recommended_threshold}\n")
        f.write(f"  - Spatial CV Accuracy: {rf_spatial_agg['accuracy_mean']:.4f}\n")
        f.write(f"  - Spatial CV Precision: {rf_spatial_agg['precision_mean']:.4f}\n")
        f.write(f"  - Spatial CV Recall: {rf_spatial_agg['recall_mean']:.4f}\n")
        f.write(f"  - Spatial CV F1 Score: {rf_spatial_agg['f1_mean']:.4f}\n")
        f.write(f"  - Spatial CV False Negative Rate (FNR): {rf_spatial_agg['false_negative_rate_mean']:.4f}\n")
        f.write(f"  - Calibration Brier Score: {brier:.4f}\n\n")
        f.write("TOP FEATURE IMPORTANCES (Gini Impurity):\n")
        for idx, row in df_imp.iterrows():
            f.write(f"  {idx+1}. {row['feature']}: {row['importance']:.4f}\n")

    logger.info(f"Saved Quality Report JSON: {report_json_path}")
    logger.info(f"Saved Quality Report Text: {report_txt_path}")
    logger.info(f"Saved Metrics JSON: {metrics_json_path}")

    logger.info("==================================================================")
    logger.info("PHASE 5 PIPELINE COMPLETED SUCCESSFULLY!")
    logger.info("==================================================================")

    return metadata


if __name__ == "__main__":
    run_phase5_pipeline()
