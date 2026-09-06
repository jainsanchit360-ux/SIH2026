"""Model Evaluation Module.

Computes classification metrics for static landslide susceptibility models:
- Confusion Matrix & False Negative Rate (FNR) analysis for hazard screening
- Precision, Recall, F1-Score, ROC-AUC Score
- Threshold tradeoff analysis
- Probability calibration curve and Brier score
"""

from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.calibration import calibration_curve


def evaluate_susceptibility_model(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """Evaluate static susceptibility model performance.

    Parameters
    ----------
    y_true : np.ndarray
        Ground truth labels (1: historical landslide point, 0: background/control sample).
    y_pred : np.ndarray
        Predicted binary class labels.
    y_prob : np.ndarray
        Predicted probability scores [0.0, 1.0].
    threshold : float
        Decision threshold for binary classification.

    Returns
    -------
    Dict[str, Any]
        Dictionary of comprehensive evaluation metrics.
    """
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)
    
    # Apply threshold if y_pred derived from y_prob
    if y_pred is None:
        y_pred = (y_prob >= threshold).astype(int)
    else:
        y_pred = np.asarray(y_pred).astype(int)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    acc = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    
    try:
        roc_auc = float(roc_auc_score(y_true, y_prob))
    except ValueError:
        roc_auc = 0.5

    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    brier = float(brier_score_loss(y_true, y_prob))

    return {
        "threshold": float(threshold),
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "specificity": spec,
        "roc_auc": roc_auc,
        "brier_score": brier,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "false_negative_rate": fnr,
        "false_positive_rate": fpr,
        "total_samples": int(len(y_true)),
        "positives": int(np.sum(y_true == 1)),
        "controls": int(np.sum(y_true == 0)),
    }


def compute_probability_distribution_stats(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> Dict[str, Any]:
    """Compute probability summary statistics for ground truth positive vs control classes.

    Parameters
    ----------
    y_true : np.ndarray
        Ground truth binary labels.
    y_prob : np.ndarray
        Predicted probabilities.

    Returns
    -------
    Dict[str, Any]
        Dictionary with 'positives' and 'controls' stats (mean, std, median, p5, p25, p75, p95).
    """
    pos_probs = y_prob[y_true == 1]
    ctrl_probs = y_prob[y_true == 0]

    def _get_stats(arr: np.ndarray) -> Dict[str, float]:
        if len(arr) == 0:
            return {}
        return {
            "count": int(len(arr)),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "median": float(np.median(arr)),
            "p5": float(np.percentile(arr, 5)),
            "p25": float(np.percentile(arr, 25)),
            "p75": float(np.percentile(arr, 75)),
            "p95": float(np.percentile(arr, 95)),
        }

    return {
        "positives": _get_stats(pos_probs),
        "controls": _get_stats(ctrl_probs),
    }


def analyze_threshold_tradeoffs(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    thresholds: List[float] = [0.30, 0.40, 0.50, 0.60, 0.70],
) -> pd.DataFrame:
    """Analyze evaluation metrics across multiple classification thresholds.

    Parameters
    ----------
    y_true : np.ndarray
        Ground truth binary labels.
    y_prob : np.ndarray
        Predicted probabilities for positive class.
    thresholds : List[float]
        List of decision threshold values to evaluate.

    Returns
    -------
    pd.DataFrame
        DataFrame summarizing metrics across thresholds.
    """
    records = []
    for th in thresholds:
        y_pred = (y_prob >= th).astype(int)
        res = evaluate_susceptibility_model(y_true, y_pred, y_prob, threshold=th)
        records.append(res)
    return pd.DataFrame(records)


def compute_calibration_data(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Compute calibration curve points and Brier score loss.

    Parameters
    ----------
    y_true : np.ndarray
        Ground truth binary labels.
    y_prob : np.ndarray
        Predicted probabilities.
    n_bins : int
        Number of probability bins.

    Returns
    -------
    Tuple[np.ndarray, np.ndarray, float]
        (prob_true, prob_pred, brier_score)
    """
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="uniform")
    brier = float(brier_score_loss(y_true, y_prob))
    return prob_true, prob_pred, brier

