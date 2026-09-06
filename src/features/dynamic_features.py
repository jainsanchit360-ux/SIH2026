"""Dynamic feature engineering module (Layer 2 Trigger Features).

Calculates antecedent precipitation indicators (1-day, 3-day, 7-day accumulated rainfall)
from NASA GPM IMERG daily rasters and volumetric soil moisture from NASA SMAP.
"""

import pandas as pd


def compute_dynamic_trigger_features(
    rainfall_1d_mm: float,
    rainfall_3d_mm: float,
    rainfall_7d_mm: float,
    soil_moisture_percentage: float
) -> pd.DataFrame:
    """Construct dynamic trigger feature representation for a given timestamp and location.

    Parameters
    ----------
    rainfall_1d_mm : float
        1-day accumulated precipitation in millimeters.
    rainfall_3d_mm : float
        3-day accumulated precipitation in millimeters.
    rainfall_7d_mm : float
        7-day accumulated precipitation in millimeters.
    soil_moisture_percentage : float
        Current volumetric soil moisture percentage (0-100%).

    Returns
    -------
    pd.DataFrame
        Single-row DataFrame containing dynamic environmental trigger indicators.
    """
    return pd.DataFrame([{
        "rainfall_1d_mm": rainfall_1d_mm,
        "rainfall_3d_mm": rainfall_3d_mm,
        "rainfall_7d_mm": rainfall_7d_mm,
        "soil_moisture_pct": soil_moisture_percentage
    }])
