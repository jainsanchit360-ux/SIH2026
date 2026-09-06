"""PHASE 4 — HISTORICAL LANDSLIDE DENSITY & SPATIAL BACKGROUND/CONTROL SAMPLING PIPELINE

Generates state-stratified background control samples across the North-Eastern Region (NER),
enforces a 500m exclusion buffer from known historical GSI landslides, extracts SRTM terrain,
computes historical landslide density and spatial proximity features (with self-exclusion logic),
assigns ~30km spatial cross-validation blocks, and exports the unified spatial susceptibility dataset.
"""

import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import matplotlib
matplotlib.use("Agg")  # Non-interactive background plotting
import matplotlib.pyplot as plt
import seaborn as sns

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config.settings import get_settings
from src.data.loaders.dem_loader import SRTMTileIndex, discover_srtm_archives, parse_tile_bounds
from src.geo.sampling import generate_background_samples
from src.geo.spatial_features import compute_historical_features
from src.features.static_features import assemble_susceptibility_dataset

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("generate_spatial_samples")

settings = get_settings()


def generate_phase4_figures(
    df_dataset: pd.DataFrame,
    audit_stats: Dict[str, Any],
    figures_dir: Path,
) -> List[Path]:
    """Generate high-resolution diagnostic figures for Phase 4."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", palette="muted")
    saved_paths = []

    positives = df_dataset[df_dataset["target"] == 1]
    controls = df_dataset[df_dataset["target"] == 0]

    # 1. background_sample_distribution.png (Positives vs Controls per State)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Barplot by state
    state_df = df_dataset.groupby(["state_clean", "sample_type"]).size().reset_index(name="count")
    sns.barplot(
        data=state_df,
        x="state_clean",
        y="count",
        hue="sample_type",
        palette={"historical_landslide": "#d95f02", "background_control": "#7570b3"},
        ax=axes[0],
    )
    axes[0].set_title("Sample Breakdown by State (NER)", fontsize=13, fontweight="bold", pad=12)
    axes[0].set_xlabel("North Eastern State", fontsize=11)
    axes[0].set_ylabel("Number of Samples", fontsize=11)
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].legend(title="Sample Type")

    # Spatial scatter plot
    axes[1].scatter(
        controls["lon_num"],
        controls["lat_num"],
        c="#7570b3",
        alpha=0.4,
        s=12,
        label=f"Background Controls (n={len(controls):,})",
    )
    axes[1].scatter(
        positives["lon_num"],
        positives["lat_num"],
        c="#d95f02",
        alpha=0.6,
        s=14,
        label=f"Historical Landslides (n={len(positives):,})",
    )
    axes[1].set_title("Geographic Distribution of Spatial Samples", fontsize=13, fontweight="bold", pad=12)
    axes[1].set_xlabel("Longitude (°E)", fontsize=11)
    axes[1].set_ylabel("Latitude (°N)", fontsize=11)
    axes[1].legend(loc="upper right")

    plt.tight_layout()
    fig_path1 = figures_dir / "background_sample_distribution.png"
    plt.savefig(fig_path1, dpi=300)
    plt.close()
    saved_paths.append(fig_path1)
    logger.info(f"Saved figure: {fig_path1}")

    # 2. nearest_landslide_distance_hist.png (Exclusion buffer validation)
    plt.figure(figsize=(10, 6))
    sns.histplot(
        data=controls,
        x="nearest_landslide_distance_m",
        color="#7570b3",
        kde=True,
        bins=50,
        label="Background Controls",
        element="step",
    )
    sns.histplot(
        data=positives,
        x="nearest_landslide_distance_m",
        color="#d95f02",
        kde=True,
        bins=50,
        label="Historical Landslides (Self-Excluded)",
        element="step",
    )
    plt.axvline(
        x=500.0,
        color="red",
        linestyle="--",
        linewidth=2,
        label="500m Minimum Exclusion Buffer",
    )
    plt.title(
        "Nearest Landslide Distance Distribution (Verifying 500m Exclusion Buffer)",
        fontsize=13,
        fontweight="bold",
        pad=15,
    )
    plt.xlabel("Distance to Nearest Historical Landslide (meters)", fontsize=11)
    plt.ylabel("Sample Count", fontsize=11)
    plt.legend(fontsize=10)
    plt.tight_layout()
    fig_path2 = figures_dir / "nearest_landslide_distance_hist.png"
    plt.savefig(fig_path2, dpi=300)
    plt.close()
    saved_paths.append(fig_path2)
    logger.info(f"Saved figure: {fig_path2}")

    # 3. landslide_density_map.png (Landslide density distribution 5km)
    plt.figure(figsize=(10, 7))
    sc = plt.scatter(
        df_dataset["lon_num"],
        df_dataset["lat_num"],
        c=df_dataset["historical_count_5km"],
        cmap="YlOrRd",
        s=15,
        alpha=0.7,
    )
    cbar = plt.colorbar(sc)
    cbar.set_label("Historical Landslides within 5km Radius", fontsize=11)
    plt.title("Spatial Landslide Density (5km Radius)", fontsize=13, fontweight="bold", pad=15)
    plt.xlabel("Longitude (°E)", fontsize=11)
    plt.ylabel("Latitude (°N)", fontsize=11)
    plt.tight_layout()
    fig_path3 = figures_dir / "landslide_density_map.png"
    plt.savefig(fig_path3, dpi=300)
    plt.close()
    saved_paths.append(fig_path3)
    logger.info(f"Saved figure: {fig_path3}")

    return saved_paths


def run_phase4_pipeline() -> Dict[str, Any]:
    """Execute complete Phase 4 pipeline."""
    start_time = time.time()
    logger.info("==================================================================")
    logger.info("STARTING PHASE 4 — SPATIAL SAMPLING & DENSITY PIPELINE")
    logger.info("==================================================================")

    processed_dir = settings.DATA_PROCESSED_DIR
    raw_dem_dir = settings.DEM_DATA_DIR
    extracted_dem_dir = settings.DATA_INTERIM_DIR / "dem_extracted"
    reports_dir = BASE_DIR / "reports"
    figures_dir = reports_dir / "figures"

    # Step 1: Load Phase 3 Positive Historical Landslides
    gsi_parquet_path = processed_dir / "gsi_landslides_ner_terrain.parquet"
    if not gsi_parquet_path.exists():
        # Fallback to Phase 2 Parquet if Phase 3 not present
        gsi_parquet_path = processed_dir / "gsi_landslides_ner.parquet"

    if not gsi_parquet_path.exists():
        raise FileNotFoundError(
            f"Required GSI landslide dataset not found at {gsi_parquet_path}. "
            "Please run Phase 2 / Phase 3 pipeline first."
        )

    logger.info(f"Loading GSI historical landslide dataset from: {gsi_parquet_path}")
    df_positives = pd.read_parquet(gsi_parquet_path)
    logger.info(f"Loaded {len(df_positives):,} positive historical landslide observations.")

    # Step 2: Initialize DEM Tile Index
    tile_index = SRTMTileIndex()
    
    # 2a. Index extracted .hgt files
    if extracted_dem_dir.exists():
        hgt_files = list(extracted_dem_dir.glob("*.hgt"))
        for hgt_f in hgt_files:
            info = parse_tile_bounds(hgt_f.name)
            tile_index.add_tile(info, hgt_f)

    # 2b. Index zip archives directly if needed
    if len(tile_index.tiles) == 0 and raw_dem_dir.exists():
        zip_archives = discover_srtm_archives(raw_dem_dir)
        logger.info(f"Discovered {len(zip_archives)} SRTM zip archives in {raw_dem_dir}")
        for archive_path in zip_archives:
            info = parse_tile_bounds(archive_path.name)
            tile_index.add_tile(info, archive_path)

    logger.info(f"Indexed {len(tile_index.tiles)} SRTM DEM tiles across NER study area.")

    # Step 3: Generate Background Control Samples
    logger.info("Generating state-stratified background control samples (target ratio=1.0, exclusion=500m)...")
    df_background, audit_stats = generate_background_samples(
        historical_gsi_df=df_positives,
        tile_index=tile_index,
        target_ratio=1.0,
        exclusion_distance_m=500.0,
        random_seed=42,
    )

    logger.info(f"Generated {len(df_background):,} valid background control samples.")

    # Step 4: Compute Spatial Proximity & Density Features
    logger.info("Computing spatial features (proximity & density counts) for positive samples with self-exclusion...")
    pos_spatial_features = compute_historical_features(
        query_df=df_positives,
        reference_landslides_df=df_positives,
        self_exclusion=True,
        radii_km=[1.0, 2.0, 5.0, 10.0],
    )

    logger.info("Computing spatial features for background control samples...")
    bg_spatial_features = compute_historical_features(
        query_df=df_background,
        reference_landslides_df=df_positives,
        self_exclusion=False,
        radii_km=[1.0, 2.0, 5.0, 10.0],
    )

    # Step 5: Assemble Static Susceptibility Dataset
    logger.info("Assembling unified static susceptibility dataset...")
    full_dataset = assemble_susceptibility_dataset(
        positives_df=df_positives,
        background_df=df_background,
        pos_spatial_features=pos_spatial_features,
        bg_spatial_features=bg_spatial_features,
    )

    logger.info(
        f"Unified dataset assembled: {len(full_dataset):,} total rows "
        f"({(full_dataset['target'] == 1).sum():,} Positives, {(full_dataset['target'] == 0).sum():,} Controls)."
    )

    # Step 6: Export Datasets
    parquet_out = processed_dir / "spatial_susceptibility_dataset.parquet"
    csv_out = processed_dir / "spatial_susceptibility_dataset.csv"
    geojson_out = processed_dir / "spatial_susceptibility_dataset.geojson"

    full_dataset.to_parquet(parquet_out, index=False)
    full_dataset.to_csv(csv_out, index=False)

    geometry = [Point(xy) for xy in zip(full_dataset["lon_num"], full_dataset["lat_num"])]
    gdf = gpd.GeoDataFrame(full_dataset, geometry=geometry, crs="EPSG:4326")
    gdf.to_file(geojson_out, driver="GeoJSON")

    logger.info(f"Exported Parquet: {parquet_out}")
    logger.info(f"Exported CSV: {csv_out}")
    logger.info(f"Exported GeoJSON: {geojson_out}")

    # Step 7: Generate Figures & Quality Reports
    logger.info("Generating diagnostic figures...")
    generate_phase4_figures(full_dataset, audit_stats, figures_dir)

    elapsed = time.time() - start_time
    report_json_path = reports_dir / "spatial_sampling_report.json"
    report_txt_path = reports_dir / "spatial_sampling_report.txt"

    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(elapsed, 2),
        "total_samples": len(full_dataset),
        "positive_landslides": int((full_dataset["target"] == 1).sum()),
        "background_controls": int((full_dataset["target"] == 0).sum()),
        "class_balance_ratio": float((full_dataset["target"] == 0).sum() / (full_dataset["target"] == 1).sum()),
        "spatial_blocks_count": int(full_dataset["spatial_block_id"].nunique()),
        "audit_sampling_stats": audit_stats,
    }

    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    with open(report_txt_path, "w", encoding="utf-8") as f:
        f.write("RESQTECH PHASE 4 — SPATIAL SAMPLING & DENSITY REPORT\n")
        f.write("====================================================\n\n")
        f.write(f"Timestamp: {report_data['timestamp']}\n")
        f.write(f"Pipeline Runtime: {report_data['elapsed_seconds']} seconds\n\n")
        f.write(f"Total Unified Samples: {report_data['total_samples']:,}\n")
        f.write(f"  - Positive Landslides (target=1): {report_data['positive_landslides']:,}\n")
        f.write(f"  - Background Controls (target=0): {report_data['background_controls']:,}\n")
        f.write(f"Class Ratio (Control/Pos): {report_data['class_balance_ratio']:.2f}\n")
        f.write(f"Spatial CV Blocks (~30km x 30km): {report_data['spatial_blocks_count']}\n\n")
        f.write("Sampling Audit Statistics:\n")
        f.write(f"  - Total Target Controls Requested: {audit_stats['total_target_controls']:,}\n")
        f.write(f"  - Controls Generated: {audit_stats['controls_generated']:,}\n")
        f.write(f"  - Candidate Attempts: {audit_stats['candidate_attempts']:,}\n")
        f.write(f"  - Rejected (Out of DEM bounds): {audit_stats['rejected_uncovered_dem']:,}\n")
        f.write(f"  - Rejected (Within 500m Exclusion Buffer): {audit_stats['rejected_exclusion_buffer']:,}\n")
        f.write(f"  - Rejected (NoData Terrain): {audit_stats['rejected_nodata_terrain']:,}\n")

    logger.info(f"Saved Quality Report JSON: {report_json_path}")
    logger.info(f"Saved Quality Report Text: {report_txt_path}")

    logger.info("==================================================================")
    logger.info("PHASE 4 PIPELINE COMPLETED SUCCESSFULLY!")
    logger.info("==================================================================")

    return report_data


if __name__ == "__main__":
    run_phase4_pipeline()
