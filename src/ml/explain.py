"""Model Explainability & Feature Attribution Module.

Provides model feature importance ranking, permutation importances on spatial validation data,
and single-observation risk driver explanation narratives for static susceptibility predictions.
"""

from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance


def get_feature_importances(
    model_obj: Any,
    feature_names: List[str],
) -> pd.DataFrame:
    """Extract impurity-based feature importance ranking from tree models.

    Parameters
    ----------
    model_obj : Any
        Trained tree-based classifier instance.
    feature_names : List[str]
        List of predictor feature names.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns ['feature', 'importance'] sorted descending.
    """
    if hasattr(model_obj, "feature_importances_"):
        importances = model_obj.feature_importances_
    else:
        importances = np.zeros(len(feature_names))

    df_imp = pd.DataFrame(
        {"feature": feature_names, "importance": importances}
    ).sort_values(by="importance", ascending=False).reset_index(drop=True)
    
    return df_imp


def compute_permutation_importances(
    model_obj: Any,
    X_val: pd.DataFrame,
    y_val: np.ndarray,
    feature_names: List[str],
    scoring: str = "roc_auc",
    n_repeats: int = 5,
    random_state: int = 42,
) -> pd.DataFrame:
    """Compute permutation feature importances on spatial validation data.

    Parameters
    ----------
    model_obj : Any
        Trained model instance.
    X_val : pd.DataFrame
        Validation predictor matrix.
    y_val : np.ndarray
        Validation ground truth labels.
    feature_names : List[str]
        Feature names.
    scoring : str
        Scoring metric for permutation importance.
    n_repeats : int
        Number of permutation repeats.
    random_state : int
        Random seed.

    Returns
    -------
    pd.DataFrame
        DataFrame with ['feature', 'perm_importance_mean', 'perm_importance_std'].
    """
    result = permutation_importance(
        model_obj,
        X_val,
        y_val,
        scoring=scoring,
        n_repeats=n_repeats,
        random_state=random_state,
        n_jobs=-1,
    )

    df_perm = pd.DataFrame(
        {
            "feature": feature_names,
            "perm_importance_mean": result.importances_mean,
            "perm_importance_std": result.importances_std,
        }
    ).sort_values(by="perm_importance_mean", ascending=False).reset_index(drop=True)

    return df_perm


def explain_susceptibility_prediction(
    model_obj: Any,
    feature_names: List[str],
    feature_dict: Dict[str, Any],
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """Generate qualitative explanation narrative and risk drivers for a single coordinate location.

    Parameters
    ----------
    model_obj : Any
        Trained susceptibility model.
    feature_names : List[str]
        Predictor feature list.
    feature_dict : Dict[str, Any]
        Dictionary of feature values for query point.
    threshold : float
        Prototype binary threshold.

    Returns
    -------
    Dict[str, Any]
        Explanation dictionary containing score, probability, risk level, top drivers, and narrative.
    """
    # Assemble single row DataFrame
    X_query = pd.DataFrame([feature_dict])[feature_names]

    # Predict probability
    prob = float(model_obj.predict_proba(X_query)[0, 1])
    score = round(prob * 100.0, 1)

    # Classify prototype category
    if score >= 70.0:
        category = "HIGH"
    elif score >= 40.0:
        category = "MODERATE"
    else:
        category = "LOW"

    # Feature importance context
    df_imp = get_feature_importances(model_obj, feature_names)
    
    # Identify top risk drivers present in input
    drivers = []
    slope = feature_dict.get("slope_deg", 0.0)
    nearest_dist = feature_dict.get("nearest_landslide_distance_m", 99999.0)
    density_5km = feature_dict.get("historical_count_5km", 0)
    density_1km = feature_dict.get("historical_count_1km", 0)
    elevation = feature_dict.get("elevation_m", 0.0)

    if slope >= 25.0:
        drivers.append(f"Steep terrain slope ({slope:.1f}°)")
    elif slope >= 15.0:
        drivers.append(f"Moderate terrain slope ({slope:.1f}°)")

    if nearest_dist <= 2000.0:
        drivers.append(f"High proximity to known historical landslide ({nearest_dist:.0f}m)")

    if density_5km >= 5:
        drivers.append(f"Dense historical landslide concentration in 5km radius ({density_5km} records)")
    elif density_1km >= 1:
        drivers.append(f"Known historical landslide within 1km radius ({density_1km} record)")

    if not drivers:
        drivers.append("Terrain slope and regional spatial context")

    narrative = (
        f"Location evaluated with static susceptibility score of {score}/100 ({category} Susceptibility). "
        f"Key risk drivers: {'; '.join(drivers)}."
    )

    return {
        "susceptibility_score": score,
        "susceptibility_probability": prob,
        "prototype_category": category,
        "threshold_used": threshold,
        "is_susceptible_prototype": bool(prob >= threshold),
        "primary_risk_drivers": drivers,
        "explanation_narrative": narrative,
        "feature_values": {k: feature_dict[k] for k in feature_names if k in feature_dict},
    }
