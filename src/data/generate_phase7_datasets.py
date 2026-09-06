"""Dataset Generator for Phase 7 Current Landslide Risk Fusion.

Processes Phase 6 dynamic environmental observations across North-Eastern Region (NER) pilot locations,
evaluates Layer 1 Phase 5B static susceptibility models, computes deterministic two-layer risk fusion,
derives temporal trend analytics across consecutive dates, and saves output Parquet and CSV datasets.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any
import numpy as np
import pandas as pd
from scipy.spatial import KDTree

from src.config.settings import get_settings
from src.risk.susceptibility import StaticSusceptibilityEngine
from src.risk.trigger_engine import DynamicTriggerEngine
from src.risk.risk_fusion import RiskFusionEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_phase7_risk_dataset() -> Tuple[pd.DataFrame, Path, Path]:
    """Generate Phase 7 current landslide risk dataset combining static and dynamic layers."""
    settings = get_settings()
    processed_dir = settings.DATA_PROCESSED_DIR

    dynamic_parquet_path = processed_dir / "dynamic_environmental_features.parquet"
    spatial_parquet_path = processed_dir / "spatial_susceptibility_dataset.parquet"

    if not dynamic_parquet_path.exists():
        raise FileNotFoundError(
            f"Phase 6 dynamic environmental dataset not found at {dynamic_parquet_path}."
        )

    if not spatial_parquet_path.exists():
        raise FileNotFoundError(
            f"Spatial susceptibility dataset not found at {spatial_parquet_path}."
        )

    logger.info("Loading Phase 6 dynamic environmental features and spatial susceptibility datasets...")
    df_dynamic = pd.read_parquet(dynamic_parquet_path)
    df_spatial = pd.read_parquet(spatial_parquet_path)

    # Build KDTree for spatial terrain lookup
    spatial_coords = df_spatial[["latitude", "longitude"]].values
    tree = KDTree(spatial_coords)

    # Initialize risk engines
    susceptibility_engine = StaticSusceptibilityEngine()
    trigger_engine = DynamicTriggerEngine()
    fusion_engine = RiskFusionEngine()

    # Pre-evaluate static susceptibility per unique site
    unique_sites = df_dynamic[["site_id", "site_name", "state", "latitude", "longitude"]].drop_duplicates()
    site_static_cache: Dict[str, Dict[str, Any]] = {}

    for _, site_row in unique_sites.iterrows():
        site_id = str(site_row["site_id"])
        lat = float(site_row["latitude"])
        lon = float(site_row["longitude"])

        # Nearest neighbor lookup in spatial dataset
        dist_deg, nearest_idx = tree.query([lat, lon])
        nearest_record = df_spatial.iloc[nearest_idx]

        district = str(nearest_record.get("district", "NER Region"))
        elev = float(nearest_record.get("elevation_m", np.nan))
        slope = float(nearest_record.get("slope_deg", np.nan))
        h5k = float(nearest_record.get("historical_count_5km", np.nan))
        h10k = float(nearest_record.get("historical_count_10km", np.nan))

        static_eval = susceptibility_engine.evaluate_static_susceptibility(
            latitude=lat,
            longitude=lon,
            elevation_m=elev,
            slope_deg=slope,
            historical_count_5km=h5k,
            historical_count_10km=h10k,
        )
        static_eval["district"] = district
        site_static_cache[site_id] = static_eval

    logger.info(f"Pre-evaluated static susceptibility for {len(site_static_cache)} pilot sites.")

    # Sort dynamic dataset by site_id and date for trend tracking
    df_dynamic["observation_date"] = df_dynamic["observation_date"].astype(str)
    df_dynamic = df_dynamic.sort_values(by=["site_id", "observation_date"]).reset_index(drop=True)

    all_fused_records = []

    # Group by site to track consecutive date trends
    grouped = df_dynamic.groupby("site_id")

    for site_id, group_df in grouped:
        static_eval = site_static_cache[site_id]
        prev_score: Optional[float] = None
        prev_level: Optional[str] = None

        for _, row in group_df.iterrows():
            obs_date = str(row["observation_date"])
            r1d = float(row["rainfall_1d"]) if pd.notna(row["rainfall_1d"]) else np.nan
            r3d = float(row["rainfall_3d"]) if pd.notna(row["rainfall_3d"]) else np.nan
            r7d = float(row["rainfall_7d"]) if pd.notna(row["rainfall_7d"]) else np.nan
            sm = float(row["soil_moisture"]) if pd.notna(row["soil_moisture"]) else np.nan

            r_status = str(row.get("rainfall_data_status", "VALID"))
            sm_status = str(row.get("soil_moisture_data_status", "VALID"))

            # Calculate dynamic trigger result
            dynamic_res = trigger_engine.calculate_trigger(
                rainfall_1d=r1d,
                rainfall_3d=r3d,
                rainfall_7d=r7d,
                soil_moisture=sm,
                rainfall_data_status=r_status,
                soil_moisture_data_status=sm_status,
                observation_date=obs_date,
                source_provenance=str(row.get("rainfall_source_file", "NASA IMERG + SMAP")),
            )

            # Fuse static + dynamic layers with trend comparison
            fused = fusion_engine.fuse(
                static_result=static_eval,
                dynamic_result=dynamic_res,
                previous_risk_score=prev_score,
                previous_risk_level=prev_level,
            )

            # Attach site identification metadata
            fused["site_id"] = site_id
            fused["location_id"] = site_id
            fused["site_name"] = str(row["site_name"])
            fused["state"] = str(row["state"])
            fused["district"] = static_eval["district"]
            fused["simulation_mode"] = False
            fused["data_source"] = "REAL_SATELLITE_OBSERVATION"

            # Stringify complex dicts/lists for Parquet/CSV safety
            fused_record_output = fused.copy()
            fused_record_output["major_risk_factors"] = json.dumps(fused["major_risk_factors"])
            fused_record_output["static_contributors"] = json.dumps(fused["static_contributors"])
            fused_record_output["dynamic_contributors"] = json.dumps(fused["dynamic_contributors"])
            fused_record_output["data_completeness"] = json.dumps(fused["data_completeness"])
            fused_record_output["fusion_weights"] = json.dumps(fused["fusion_weights"])

            all_fused_records.append(fused_record_output)

            # Update previous score and level for next chronological date
            prev_score = fused["current_risk_score"]
            prev_level = fused["current_risk_level"]

    df_fused = pd.DataFrame(all_fused_records)

    # Ensure output paths
    out_parquet = processed_dir / "current_landslide_risk.parquet"
    out_csv = processed_dir / "current_landslide_risk.csv"

    df_fused.to_parquet(out_parquet, index=False)
    df_fused.to_csv(out_csv, index=False)

    logger.info(f"Successfully generated fused risk dataset with {len(df_fused)} rows.")
    logger.info(f"Parquet saved to: {out_parquet}")
    logger.info(f"CSV saved to: {out_csv}")

    return df_fused, out_parquet, out_csv


if __name__ == "__main__":
    generate_phase7_risk_dataset()
