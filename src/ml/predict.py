"""Susceptibility Model Inference Module.

Executes static susceptibility inference on feature DataFrames or single coordinate feature dictionaries,
scaling probabilities to 0-100 scores and prototype UI susceptibility categories.
"""

from typing import Dict, List, Any, Union, Tuple, Optional
import numpy as np
import pandas as pd


def classify_prototype_category(score: float) -> str:
    """Map static susceptibility score (0.0 - 100.0) to prototype UI category.

    Thresholds:
    - 0.0 - 39.9: LOW
    - 40.0 - 69.9: MODERATE
    - 70.0 - 100.0: HIGH

    Parameters
    ----------
    score : float
        Susceptibility score from 0.0 to 100.0.

    Returns
    -------
    str
        Prototype category label ('LOW', 'MODERATE', 'HIGH').
    """
    if score >= 70.0:
        return "HIGH"
    elif score >= 40.0:
        return "MODERATE"
    else:
        return "LOW"


def predict_susceptibility_score(
    model_obj: Any,
    features_df: pd.DataFrame,
    feature_names: Optional[List[str]] = None,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Predict landslide susceptibility probabilities and 0-100 scores.

    Parameters
    ----------
    model_obj : Any
        Trained model instance (e.g., RandomForestClassifier, GradientBoostingClassifier).
    features_df : pd.DataFrame
        DataFrame of predictor features.
    feature_names : List[str], optional
        List of required feature columns to extract.

    Returns
    -------
    Tuple[np.ndarray, np.ndarray, List[str]]
        (probabilities, scores_0_100, prototype_categories)
    """
    if feature_names is not None:
        X = features_df[feature_names]
    else:
        X = features_df

    probs = model_obj.predict_proba(X)[:, 1]
    scores = np.round(probs * 100.0, 1)
    categories = [classify_prototype_category(s) for s in scores]

    return probs, scores, categories


def predict_susceptibility_single(
    model_obj: Any,
    feature_names: List[str],
    feature_dict: Dict[str, Any],
    model_version: str = "1.0.0",
) -> Dict[str, Any]:
    """Single observation inference interface for backend API integration.

    Parameters
    ----------
    model_obj : Any
        Trained susceptibility classifier.
    feature_names : List[str]
        Required feature names list.
    feature_dict : Dict[str, Any]
        Feature key-value dictionary.
    model_version : str
        Model metadata version tag.

    Returns
    -------
    Dict[str, Any]
        Inference result dictionary.
    """
    df_single = pd.DataFrame([feature_dict])[feature_names]
    probs, scores, categories = predict_susceptibility_score(model_obj, df_single)
    
    prob = float(probs[0])
    score = float(scores[0])
    category = categories[0]

    return {
        "susceptibility_score": score,
        "susceptibility_probability": prob,
        "prototype_category": category,
        "model_version": model_version,
    }
