"""Dataset generator for Phase 6 Dynamic Environmental Data Processing.

Processes real satellite observations (NASA IMERG rainfall + NASA SMAP soil moisture)
over North-Eastern Region (NER) pilot locations across available overlapping dates,
calculates dynamic trigger scores, and outputs Parquet and CSV files along with
an offline demo cache.
"""

from datetime import date
import json
import logging
from pathlib import Path
from typing import List, Dict
import numpy as np
import pandas as pd

from src.config.settings import get_settings
from src.data.processors.temporal_alignment import TemporalAligner
from src.risk.trigger_engine import DynamicTriggerEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_phase6_datasets():
    """Generate dynamic environmental feature dataset and offline demo cache."""
    settings = get_settings()
    output_dir = settings.DATA_PROCESSED_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    aligner = TemporalAligner()
    trigger_engine = DynamicTriggerEngine()

    # Define key NER state capitals / pilot study locations
    pilot_locations = [
        {"site_id": "NER_PILOT_01", "site_name": "Gangtok, Sikkim", "state": "Sikkim", "latitude": 27.33, "longitude": 88.61},
        {"site_id": "NER_PILOT_02", "site_name": "Guwahati, Assam", "state": "Assam", "latitude": 26.14, "longitude": 91.73},
        {"site_id": "NER_PILOT_03", "site_name": "Shillong, Meghalaya", "state": "Meghalaya", "latitude": 25.57, "longitude": 91.88},
        {"site_id": "NER_PILOT_04", "site_name": "Aizawl, Mizoram", "state": "Mizoram", "latitude": 23.73, "longitude": 92.71},
        {"site_id": "NER_PILOT_05", "site_name": "Kohima, Nagaland", "state": "Nagaland", "latitude": 25.67, "longitude": 94.11},
        {"site_id": "NER_PILOT_06", "site_name": "Imphal, Manipur", "state": "Manipur", "latitude": 24.81, "longitude": 93.94},
        {"site_id": "NER_PILOT_07", "site_name": "Itanagar, Arunachal Pradesh", "state": "Arunachal Pradesh", "latitude": 27.08, "longitude": 93.61},
        {"site_id": "NER_PILOT_08", "site_name": "Agartala, Tripura", "state": "Tripura", "latitude": 23.83, "longitude": 91.28},
    ]

    # Additional historical landslide sites from GSI dataset
    gsi_parquet_path = output_dir / "gsi_landslides_ner.parquet"
    if gsi_parquet_path.exists():
        try:
            gsi_df = pd.read_parquet(gsi_parquet_path)
            valid_gsi = gsi_df[gsi_df["is_valid_coord"] == True].head(7)
            for idx, row in valid_gsi.iterrows():
                pilot_locations.append({
                    "site_id": f"GSI_SITE_{idx+1:02d}",
                    "site_name": f"{row.get('slide_name', 'GSI Landslide Site')} ({row.get('district', 'NER')})",
                    "state": str(row.get('state_clean', row.get('state', 'NER'))),
                    "latitude": float(row['latitude']),
                    "longitude": float(row['longitude']),
                })
        except Exception as e:
            logger.warning(f"Could not load GSI parquet for additional pilot points: {e}")

    # Discover available overlapping dates
    imerg_dates = set(aligner.imerg_proc._date_to_file.keys())
    smap_dates = set(aligner.smap_proc._date_to_file.keys())
    overlapping_dates = sorted(list(imerg_dates.intersection(smap_dates)))

    logger.info(f"Generating feature records for {len(pilot_locations)} locations across {len(overlapping_dates)} dates...")

    all_records = []

    for obs_d in overlapping_dates:
        # Use batch alignment per date for maximum IO efficiency
        batch_df = aligner.align_batch(pilot_locations, obs_d)
        for _, row in batch_df.iterrows():
            rec = row.to_dict()

            # Calculate trigger outputs
            trig_res = trigger_engine.calculate_trigger(
                rainfall_1d=rec["rainfall_1d"],
                rainfall_3d=rec["rainfall_3d"],
                rainfall_7d=rec["rainfall_7d"],
                soil_moisture=rec["soil_moisture"],
                rainfall_data_status=rec["rainfall_data_status"],
                soil_moisture_data_status=rec["soil_moisture_data_status"],
            )

            rec["dynamic_trigger_score"] = trig_res["dynamic_trigger_score"]
            rec["dynamic_trigger_level"] = trig_res["dynamic_trigger_level"]
            rec["major_trigger_factors"] = json.dumps(trig_res["major_trigger_factors"])
            rec["calibration_disclaimer"] = trig_res["calibration_disclaimer"]

            all_records.append(rec)

    df_features = pd.DataFrame(all_records)

    # Output paths
    parquet_path = output_dir / "dynamic_environmental_features.parquet"
    csv_path = output_dir / "dynamic_environmental_features.csv"

    df_features.to_parquet(parquet_path, index=False)
    df_features.to_csv(csv_path, index=False)

    logger.info(f"Saved dynamic environmental dataset to {parquet_path} ({len(df_features)} rows)")

    # Generate offline demo cache
    demo_dates = overlapping_dates[:5] if len(overlapping_dates) >= 5 else overlapping_dates
    demo_df = df_features[df_features["observation_date"].isin([d.strftime("%Y-%m-%d") for d in demo_dates])].copy()

    demo_parquet_path = output_dir / "demo_dynamic_environmental_cache.parquet"
    demo_json_path = output_dir / "demo_dynamic_environmental_cache.json"

    demo_df.to_parquet(demo_parquet_path, index=False)

    demo_json_data = demo_df.to_dict(orient="records")
    with open(demo_json_path, "w") as f:
        json.dump(demo_json_data, f, indent=2)

    logger.info(f"Saved offline demo cache to {demo_parquet_path} and {demo_json_path} ({len(demo_df)} rows)")

    return df_features, demo_df


if __name__ == "__main__":
    generate_phase6_datasets()
