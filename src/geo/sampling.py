"""Spatial sampling module for generating background/control samples.

Generates background/control samples across the valid North-Eastern Region (NER)
study area while enforcing a strict exclusion buffer from known historical GSI landslide points.

NOTE: Background samples represent unannotated regional terrain points used for contrastive
susceptibility learning and MUST NOT be labeled as "confirmed non-landslide locations".
"""

import math
import logging
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from src.config.settings import get_settings
from src.data.loaders.dem_loader import SRTMTileIndex, read_hgt_raster
from src.geo.spatial_features import EARTH_RADIUS_METERS
from src.geo.terrain import sample_point_terrain

logger = logging.getLogger("geo_sampling")
settings = get_settings()


def derive_ner_state_bounds(gsi_df: pd.DataFrame, buffer_deg: float = 0.05) -> Dict[str, Tuple[float, float, float, float]]:
    """Derive tight geographic bounding boxes per NER state from historical landslide points.

    Parameters
    ----------
    gsi_df : pd.DataFrame
        Historical GSI landslide dataset.
    buffer_deg : float
        Padding in degrees to add to state bounds.

    Returns
    -------
    Dict[str, Tuple[float, float, float, float]]
        Dictionary mapping state_clean -> (min_lat, max_lat, min_lon, max_lon).
    """
    state_bounds = {}
    for state, group in gsi_df.groupby("state_clean"):
        min_lat = max(18.0, float(group["lat_num"].min()) - buffer_deg)
        max_lat = min(32.0, float(group["lat_num"].max()) + buffer_deg)
        min_lon = max(87.0, float(group["lon_num"].min()) - buffer_deg)
        max_lon = min(99.0, float(group["lon_num"].max()) + buffer_deg)

        state_bounds[state] = (min_lat, max_lat, min_lon, max_lon)

    return state_bounds


def generate_background_samples(
    historical_gsi_df: pd.DataFrame,
    tile_index: SRTMTileIndex,
    target_ratio: float = 1.0,
    exclusion_distance_m: float = 500.0,
    random_seed: int = 42,
    max_attempts_factor: int = 50,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Generate state-stratified background/control points across the NER study region.

    Enforces minimum exclusion distance buffer from positive GSI landslides and extracts real
    SRTM elevation and slope directly from DEM tiles.

    Parameters
    ----------
    historical_gsi_df : pd.DataFrame
        Positive historical GSI landslide locations with lat_num, lon_num, state_clean.
    tile_index : SRTMTileIndex
        Indexed SRTM DEM tiles for spatial lookup and terrain sampling.
    target_ratio : float
        Ratio of background samples to positive samples per state (default 1.0).
    exclusion_distance_m : float
        Minimum distance in meters required from any known positive landslide.
    random_seed : int
        Random seed for reproducible sampling.
    max_attempts_factor : int
        Maximum random sampling attempts per target sample before stopping.

    Returns
    -------
    Tuple[pd.DataFrame, Dict[str, Any]]
        (background_df, audit_stats)
    """
    np.random.seed(random_seed)

    # 1. Build BallTree of positive coordinates in radians for fast exclusion check
    gsi_valid = historical_gsi_df.dropna(subset=["lat_num", "lon_num"]).copy()
    gsi_coords_rad = np.radians(gsi_valid[["lat_num", "lon_num"]].to_numpy())
    pos_tree = BallTree(gsi_coords_rad, metric="haversine")
    exclusion_rad = exclusion_distance_m / EARTH_RADIUS_METERS

    # State bounds and targets
    state_bounds = derive_ner_state_bounds(gsi_valid)
    state_pos_counts = gsi_valid["state_clean"].value_counts().to_dict()

    background_records = []
    audit_stats = {
        "total_target_controls": 0,
        "controls_generated": 0,
        "candidate_attempts": 0,
        "rejected_uncovered_dem": 0,
        "rejected_exclusion_buffer": 0,
        "rejected_nodata_terrain": 0,
        "exclusion_distance_m": exclusion_distance_m,
        "random_seed": random_seed,
        "state_breakdown": {},
    }

    # Pre-cache tile elevation grids on demand to optimize performance
    grid_cache: Dict[Tuple[int, int], np.ndarray] = {}

    for state, pos_count in state_pos_counts.items():
        target_count = int(round(pos_count * target_ratio))
        audit_stats["total_target_controls"] += target_count
        bounds = state_bounds[state]

        min_lat, max_lat, min_lon, max_lon = bounds
        state_generated = 0
        state_attempts = 0
        max_attempts = target_count * max_attempts_factor

        while state_generated < target_count and state_attempts < max_attempts:
            state_attempts += 1
            audit_stats["candidate_attempts"] += 1

            # Candidate coordinate
            cand_lat = float(np.random.uniform(min_lat, max_lat))
            cand_lon = float(np.random.uniform(min_lon, max_lon))

            # Check 1: DEM Tile Coverage
            tile_meta = tile_index.find_tile(cand_lat, cand_lon)
            if tile_meta is None:
                audit_stats["rejected_uncovered_dem"] += 1
                continue

            # Check 2: Exclusion Distance Buffer from any positive landslide
            cand_rad = np.radians([[cand_lat, cand_lon]])
            dist_rad, _ = pos_tree.query(cand_rad, k=1)
            min_dist_m = float(dist_rad[0, 0]) * EARTH_RADIUS_METERS

            if min_dist_m < exclusion_distance_m:
                audit_stats["rejected_exclusion_buffer"] += 1
                continue

            # Check 3: Extract Real SRTM Elevation and Slope
            south_key = int(math.floor(tile_meta["south_lat"]))
            west_key = int(math.floor(tile_meta["west_lon"]))
            tile_key = (south_key, west_key)

            if tile_key not in grid_cache:
                grid_cache[tile_key] = read_hgt_raster(tile_meta["hgt_path"])

            grid = grid_cache[tile_key]
            terrain_sample = sample_point_terrain(cand_lat, cand_lon, tile_meta, grid)

            if not terrain_sample["elevation_valid"] or not terrain_sample["slope_valid"]:
                audit_stats["rejected_nodata_terrain"] += 1
                continue

            # Candidate Accepted!
            state_generated += 1
            background_records.append(
                {
                    "slide_id": f"CTRL_{state[:3].upper()}_{state_generated:05d}",
                    "state": state,
                    "state_clean": state,
                    "district": f"{state} Region",
                    "latitude": cand_lat,
                    "longitude": cand_lon,
                    "lat_num": cand_lat,
                    "lon_num": cand_lon,
                    "elevation_m": terrain_sample["elevation_m"],
                    "slope_deg": terrain_sample["slope_deg"],
                    "dem_covered": True,
                    "elevation_valid": True,
                    "slope_valid": True,
                    "dem_tile": terrain_sample["dem_tile"],
                    "target": 0,
                    "sample_type": "background_control",
                    "min_distance_to_landslide_m": min_dist_m,
                }
            )

        audit_stats["state_breakdown"][state] = {
            "target": target_count,
            "generated": state_generated,
            "attempts": state_attempts,
        }

    # Clear grid cache
    grid_cache.clear()

    df_controls = pd.DataFrame(background_records)
    audit_stats["controls_generated"] = len(df_controls)

    logger.info(
        f"Generated {len(df_controls)} background controls across {len(state_pos_counts)} states "
        f"({audit_stats['candidate_attempts']} candidate attempts, "
        f"{audit_stats['rejected_uncovered_dem']} out-of-bounds, "
        f"{audit_stats['rejected_exclusion_buffer']} rejected by 500m exclusion buffer, "
        f"{audit_stats['rejected_nodata_terrain']} nodata terrain)."
    )

    return df_controls, audit_stats
