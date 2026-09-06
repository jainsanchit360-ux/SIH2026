"""PHASE 3 — SRTM TERRAIN PROCESSING PIPELINE

Discovers raw SRTM archives, safely extracts DEM tiles, compiles spatial index,
derives elevation and latitude-aware Horn slope for GSI historical landslide records,
and outputs processed datasets, reports, and figures.
"""

import json
import logging
import math
import time
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
import matplotlib
matplotlib.use("Agg")  # Non-interactive background plotting
import matplotlib.pyplot as plt
import seaborn as sns

from src.config.settings import BASE_DIR, get_settings
from src.data.loaders.dem_loader import (
    NODATA_VALUE,
    SRTMGL1_BYTE_SIZE,
    SRTMGL1_DIM,
    SRTMTileIndex,
    discover_srtm_archives,
    parse_tile_bounds,
    read_hgt_raster,
    safe_extract_archive,
)
from src.geo.terrain import sample_point_terrain

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("process_dem_terrain")

settings = get_settings()


def run_phase3_pipeline() -> Dict[str, Any]:
    """Execute complete Phase 3 pipeline."""
    start_time = time.time()
    logger.info("Starting Phase 3 SRTM Terrain Processing Pipeline...")

    # Paths
    raw_dem_dir = settings.DEM_DATA_DIR
    extracted_dem_dir = settings.DATA_INTERIM_DIR / "dem_extracted"
    processed_dir = settings.DATA_PROCESSED_DIR
    reports_dir = BASE_DIR / "reports"
    figures_dir = reports_dir / "figures"

    extracted_dem_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------
    # STEP 1 & 2: SRTM ARCHIVE DISCOVERY & EXTRACTION
    # ----------------------------------------------------
    archives = discover_srtm_archives(raw_dem_dir)
    logger.info(f"Discovered {len(archives)} raw SRTM archives in {raw_dem_dir}")

    extraction_audits = []
    tile_index = SRTMTileIndex()

    extracted_count = 0
    reused_count = 0
    corrupt_count = 0

    for archive_path in archives:
        audit = safe_extract_archive(archive_path, output_dir=extracted_dem_dir)
        extraction_audits.append(audit)

        if audit["extraction_status"] == "extracted_success":
            extracted_count += 1
            hgt_path = Path(audit["extracted_path"])
            info = parse_tile_bounds(hgt_path.name)
            tile_index.add_tile(info, hgt_path)
        elif audit["extraction_status"] == "reused_cached":
            reused_count += 1
            hgt_path = Path(audit["extracted_path"])
            info = parse_tile_bounds(hgt_path.name)
            tile_index.add_tile(info, hgt_path)
        else:
            corrupt_count += 1
            logger.warning(f"Archive issue: {audit['archive_filename']} -> {audit['extraction_status']}")

    total_valid_tiles = len(tile_index.tiles)
    logger.info(
        f"Tile extraction complete: {total_valid_tiles} valid tiles available "
        f"({extracted_count} newly extracted, {reused_count} reused from cache, {corrupt_count} invalid/corrupt)."
    )

    # ----------------------------------------------------
    # STEP 3 & 4: LOAD PHASE 2 LANDSLIDE DATASET
    # ----------------------------------------------------
    parquet_input = processed_dir / "gsi_landslides_ner.parquet"
    if parquet_input.exists():
        logger.info(f"Loading Phase 2 landslide dataset from {parquet_input}")
        df_gsi = pd.read_parquet(parquet_input)
    else:
        csv_input = processed_dir / "gsi_landslides_ner.csv"
        logger.info(f"Loading Phase 2 landslide dataset from {csv_input}")
        df_gsi = pd.read_csv(csv_input)

    total_gsi_points = len(df_gsi)
    logger.info(f"Loaded {total_gsi_points} historical landslide records.")

    # ----------------------------------------------------
    # STEP 5 & 7: COVERAGE ANALYSIS & POINT-TO-TILE MATCHING
    # ----------------------------------------------------
    df_gsi["dem_covered"] = False
    df_gsi["dem_tile"] = None
    df_gsi["elevation_m"] = np.nan
    df_gsi["slope_deg"] = np.nan
    df_gsi["elevation_valid"] = False
    df_gsi["slope_valid"] = False

    # Match each point to tile
    tile_point_map: Dict[Tuple[int, int], List[int]] = {}
    uncovered_indices = []

    for idx, row in df_gsi.iterrows():
        lat = row["lat_num"]
        lon = row["lon_num"]
        
        tile_meta = tile_index.find_tile(lat, lon)
        if tile_meta is not None:
            df_gsi.at[idx, "dem_covered"] = True
            df_gsi.at[idx, "dem_tile"] = tile_meta["tile_id"]
            
            south_key = int(math.floor(tile_meta["south_lat"]))
            west_key = int(math.floor(tile_meta["west_lon"]))
            tile_point_map.setdefault((south_key, west_key), []).append(idx)
        else:
            uncovered_indices.append(idx)

    covered_count = df_gsi["dem_covered"].sum()
    uncovered_count = total_gsi_points - covered_count
    coverage_pct = (covered_count / total_gsi_points) * 100.0 if total_gsi_points > 0 else 0.0

    logger.info(
        f"Coverage Analysis: {covered_count}/{total_gsi_points} points covered by SRTM ({coverage_pct:.2f}%). "
        f"{uncovered_count} uncovered points."
    )

    # ----------------------------------------------------
    # STEP 8 & 12: MEMORY-SAFE TERRAIN SAMPLING (TILE BY TILE)
    # ----------------------------------------------------
    logger.info("Sampling elevation and calculating Horn slope tile-by-tile...")

    for (south_key, west_key), point_indices in tile_point_map.items():
        tile_meta = tile_index.tiles[(south_key, west_key)]
        hgt_path = tile_meta["hgt_path"]

        # Read binary raster into memory for current tile
        elevation_grid = read_hgt_raster(hgt_path)

        for idx in point_indices:
            lat = df_gsi.at[idx, "lat_num"]
            lon = df_gsi.at[idx, "lon_num"]

            sample = sample_point_terrain(lat, lon, tile_meta, elevation_grid)

            df_gsi.at[idx, "elevation_m"] = sample["elevation_m"]
            df_gsi.at[idx, "slope_deg"] = sample["slope_deg"]
            df_gsi.at[idx, "elevation_valid"] = sample["elevation_valid"]
            df_gsi.at[idx, "slope_valid"] = sample["slope_valid"]

        # Free raster memory immediately
        del elevation_grid

    # ----------------------------------------------------
    # STEP 9 & 13: QUALITY CONTROL & DESCRIPTIVE STATS
    # ----------------------------------------------------
    valid_elev_mask = df_gsi["elevation_valid"]
    valid_slope_mask = df_gsi["slope_valid"]

    elev_series = df_gsi.loc[valid_elev_mask, "elevation_m"]
    slope_series = df_gsi.loc[valid_slope_mask, "slope_deg"]

    def compute_percentiles(s: pd.Series) -> Dict[str, float]:
        if len(s) == 0:
            return {}
        p = np.percentile(s, [1, 5, 25, 50, 75, 95, 99])
        return {
            "count": int(len(s)),
            "missing_count": int(total_gsi_points - len(s)),
            "min": float(s.min()),
            "max": float(s.max()),
            "mean": float(s.mean()),
            "median": float(s.median()),
            "std": float(s.std()),
            "p1": float(p[0]),
            "p5": float(p[1]),
            "p25": float(p[2]),
            "p75": float(p[4]),
            "p95": float(p[5]),
            "p99": float(p[6]),
        }

    elev_stats = compute_percentiles(elev_series)
    slope_stats = compute_percentiles(slope_series)

    # State-wise coverage breakdown
    state_coverage = (
        df_gsi.groupby("state_clean")
        .agg(
            total_points=("state_clean", "count"),
            dem_covered_points=("dem_covered", "sum"),
            mean_elevation=("elevation_m", "mean"),
            mean_slope=("slope_deg", "mean"),
        )
        .reset_index()
    )
    state_coverage["coverage_pct"] = (
        state_coverage["dem_covered_points"] / state_coverage["total_points"]
    ) * 100.0

    # Suspicious values detection
    suspicious_elev = df_gsi[valid_elev_mask & ((df_gsi["elevation_m"] < 0) | (df_gsi["elevation_m"] > 8000))]
    suspicious_slope = df_gsi[valid_slope_mask & (df_gsi["slope_deg"] > 75.0)]

    logger.info(f"Elevation stats: min={elev_stats.get('min', np.nan):.1f}m, mean={elev_stats.get('mean', np.nan):.1f}m, max={elev_stats.get('max', np.nan):.1f}m")
    logger.info(f"Slope stats: min={slope_stats.get('min', np.nan):.1f}°, mean={slope_stats.get('mean', np.nan):.1f}°, max={slope_stats.get('max', np.nan):.1f}°")

    # ----------------------------------------------------
    # STEP 16: OUTPUT DATASET EXPORT
    # ----------------------------------------------------
    out_parquet = processed_dir / "gsi_landslides_ner_terrain.parquet"
    out_csv = processed_dir / "gsi_landslides_ner_terrain.csv"
    out_geojson = processed_dir / "gsi_landslides_ner_terrain.geojson"

    logger.info(f"Exporting processed terrain dataset to {out_parquet}")
    df_gsi.to_parquet(out_parquet, index=False)
    df_gsi.to_csv(out_csv, index=False)

    # Export GeoJSON
    gdf_gsi = gpd.GeoDataFrame(
        df_gsi,
        geometry=[
            Point(lon, lat) if not (np.isnan(lat) or np.isnan(lon)) else None
            for lat, lon in zip(df_gsi["lat_num"], df_gsi["lon_num"])
        ],
        crs="EPSG:4326",
    )
    gdf_gsi.to_file(out_geojson, driver="GeoJSON")

    # ----------------------------------------------------
    # STEP 18: GENERATE REPORTS
    # ----------------------------------------------------
    elapsed_sec = time.time() - start_time

    report_dict = {
        "phase": "PHASE 3 — SRTM TERRAIN PROCESSING",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "processing_time_seconds": round(elapsed_sec, 2),
        "dem_source": "NASA/USGS SRTMGL1 (1 arc-second)",
        "discovered_archives": len(archives),
        "valid_tiles": total_valid_tiles,
        "newly_extracted_tiles": extracted_count,
        "reused_cached_tiles": reused_count,
        "corrupt_invalid_archives": corrupt_count,
        "raster_dimensions": [SRTMGL1_DIM, SRTMGL1_DIM],
        "spatial_resolution": "1 arc-second (~30m)",
        "nodata_value": NODATA_VALUE,
        "total_gsi_points": total_gsi_points,
        "dem_covered_points": int(covered_count),
        "dem_uncovered_points": int(uncovered_count),
        "coverage_percentage": round(coverage_pct, 2),
        "elevation_stats": elev_stats,
        "slope_stats": slope_stats,
        "suspicious_values": {
            "suspicious_elevation_count": len(suspicious_elev),
            "suspicious_slope_gt_75deg_count": len(suspicious_slope),
        },
        "slope_calculation_method": "Latitude-Aware Horn 3x3 Finite Difference Gradient",
        "tile_edge_strategy": "Border replication & edge-aware window slicing",
        "state_wise_coverage": state_coverage.to_dict(orient="records"),
    }

    report_json_path = reports_dir / "dem_data_quality_report.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2)

    report_txt_path = reports_dir / "dem_data_quality_report.txt"
    with open(report_txt_path, "w", encoding="utf-8") as f:
        f.write("============================================================\n")
        f.write("RESQTECH PHASE 3 — SRTM TERRAIN DATA QUALITY REPORT\n")
        f.write("============================================================\n\n")
        f.write(f"Processing Timestamp: {report_dict['timestamp']}\n")
        f.write(f"Processing Runtime  : {elapsed_sec:.2f} seconds\n")
        f.write(f"DEM Source          : {report_dict['dem_source']}\n")
        f.write(f"Discovered Archives : {len(archives)}\n")
        f.write(f"Valid DEM Tiles     : {total_valid_tiles}\n")
        f.write(f"Raster Dimensions   : {SRTMGL1_DIM} x {SRTMGL1_DIM}\n")
        f.write(f"Spatial Resolution  : {report_dict['spatial_resolution']}\n\n")

        f.write("--- COVERAGE SUMMARY ---\n")
        f.write(f"Total GSI NER Points: {total_gsi_points}\n")
        f.write(f"DEM Covered Points  : {covered_count} ({coverage_pct:.2f}%)\n")
        f.write(f"DEM Uncovered Points: {uncovered_count} ({100.0 - coverage_pct:.2f}%)\n\n")

        f.write("--- ELEVATION STATISTICS (METERS) ---\n")
        for k, v in elev_stats.items():
            f.write(f"  {k:15s}: {v}\n")
        f.write("\n")

        f.write("--- SLOPE STATISTICS (DEGREES) ---\n")
        for k, v in slope_stats.items():
            f.write(f"  {k:15s}: {v}\n")
        f.write("\n")

        f.write("--- STATE-WISE COVERAGE BREAKDOWN ---\n")
        f.write(state_coverage.to_string(index=False))
        f.write("\n\n============================================================\n")

    logger.info(f"Saved quality reports to {report_json_path} and {report_txt_path}")

    # ----------------------------------------------------
    # STEP 19: GENERATE FIGURES
    # ----------------------------------------------------
    logger.info("Generating Phase 3 diagnostic figures in reports/figures/...")

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # 1. Tile Coverage Map
    fig, ax = plt.subplots(figsize=(10, 8))
    # Draw tile boxes
    for tile_meta in tile_index.tiles.values():
        w, s, e, n = tile_meta["west_lon"], tile_meta["south_lat"], tile_meta["east_lon"], tile_meta["north_lat"]
        rect = plt.Rectangle((w, s), e - w, n - s, fill=False, edgecolor="royalblue", alpha=0.6, lw=0.8)
        ax.add_patch(rect)

    # Scatter GSI points
    ax.scatter(
        df_gsi["lon_num"],
        df_gsi["lat_num"],
        c=df_gsi["dem_covered"].map({True: "crimson", False: "gray"}),
        s=4,
        alpha=0.6,
        label="GSI Points (Covered)",
    )
    ax.set_title("SRTM DEM Tile Coverage & GSI Historical Landslide Points (NER)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_xlim(87.0, 98.0)
    ax.set_ylim(21.0, 31.0)
    fig.tight_layout()
    fig.savefig(figures_dir / "dem_tile_coverage.png", dpi=200)
    plt.close(fig)

    # 2. Elevation Distribution
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.histplot(df_gsi.loc[valid_elev_mask, "elevation_m"], kde=True, ax=ax, color="teal", bins=50)
    ax.set_title("GSI Historical Landslide Elevation Distribution (SRTM)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Elevation (meters)")
    ax.set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(figures_dir / "gsi_elevation_distribution.png", dpi=200)
    plt.close(fig)

    # 3. Slope Distribution
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.histplot(df_gsi.loc[valid_slope_mask, "slope_deg"], kde=True, ax=ax, color="darkorange", bins=50)
    ax.set_title("GSI Historical Landslide Slope Distribution (Horn's Method)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Slope (degrees)")
    ax.set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(figures_dir / "gsi_slope_distribution.png", dpi=200)
    plt.close(fig)

    # 4. Slope by State Boxplot
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.boxplot(
        data=df_gsi[valid_slope_mask],
        x="state_clean",
        y="slope_deg",
        ax=ax,
        hue="state_clean",
        legend=False,
        palette="Blues_d",
    )
    ax.set_title("Historical Landslide Terrain Slope across North-Eastern States", fontsize=12, fontweight="bold")
    ax.set_xlabel("State")
    ax.set_ylabel("Slope (degrees)")
    plt.xticks(rotation=30)
    fig.tight_layout()
    fig.savefig(figures_dir / "gsi_slope_by_state.png", dpi=200)
    plt.close(fig)

    # 5. Spatial Distribution Preview colored by elevation
    fig, ax = plt.subplots(figsize=(10, 8))
    sc = ax.scatter(
        df_gsi.loc[valid_elev_mask, "lon_num"],
        df_gsi.loc[valid_elev_mask, "lat_num"],
        c=df_gsi.loc[valid_elev_mask, "elevation_m"],
        cmap="terrain",
        s=6,
        alpha=0.8,
    )
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label("Elevation (meters)")
    ax.set_title("Spatial Distribution of GSI Landslides by Terrain Elevation", fontsize=12, fontweight="bold")
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    fig.tight_layout()
    fig.savefig(figures_dir / "gsi_terrain_spatial_distribution.png", dpi=200)
    plt.close(fig)

    logger.info(f"Phase 3 Pipeline execution completed successfully in {elapsed_sec:.2f} seconds.")
    return report_dict


if __name__ == "__main__":
    run_phase3_pipeline()
