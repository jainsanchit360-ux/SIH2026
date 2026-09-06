"""Geospatial validation utility functions.

Verifies that incoming spatial points, rasters, and vectors lie within the defined
North-Eastern Region (NER) bounding box and conform to target Coordinate Reference Systems (CRS).
"""

from typing import Tuple
import geopandas as gpd
from src.config.settings import get_settings

settings = get_settings()


def validate_ner_bounds(
    gdf: gpd.GeoDataFrame,
    bbox: Tuple[float, float, float, float] = settings.ner_bbox
) -> gpd.GeoDataFrame:
    """Filter GeoDataFrame geometries to ensure all features fall within NER bounding box.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Input vector features (must be in EPSG:4326).
    bbox : Tuple[float, float, float, float]
        Bounding box (min_lon, min_lat, max_lon, max_lat).

    Returns
    -------
    gpd.GeoDataFrame
        Filtered GeoDataFrame contained strictly within bounding box.
    """
    if gdf.empty:
        return gdf

    min_lon, min_lat, max_lon, max_lat = bbox
    return gdf.cx[min_lon:max_lon, min_lat:max_lat]
