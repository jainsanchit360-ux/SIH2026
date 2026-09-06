"""Script to orchestrate Phase 2 GSI Historical Landslide Inventory extraction, cleaning,
coordinate validation, NER filtering, quality reporting, geospatial export, and visualization.
"""

import json
import logging
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config.settings import get_settings
from src.data.loaders.gsi_loader import (
    clean_gsi_dataframe,
    export_geospatial_outputs,
    extract_gsi_pdf_raw,
    filter_ner_records,
    generate_quality_report,
    validate_coordinates,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("extract_gsi_inventory")


def generate_figures(df_clean: pd.DataFrame, df_ner: pd.DataFrame, figures_dir: Path) -> None:
    """Generate high-resolution figures for data quality and spatial distribution."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", palette="muted")

    # 1. gsi_records_by_state.png
    plt.figure(figsize=(10, 6))
    state_counts = df_ner["state_clean"].value_counts().reset_index()
    state_counts.columns = ["State", "Landslide Count"]
    
    ax = sns.barplot(data=state_counts, x="State", y="Landslide Count", palette="viridis")
    plt.title("GSI Historical Landslide Inventory — Records by State (NER)", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("North Eastern State", fontsize=12, labelpad=10)
    plt.ylabel("Number of Landslide Records", fontsize=12, labelpad=10)
    plt.xticks(rotation=30, ha="right")
    
    for p in ax.patches:
        height = int(p.get_height())
        if height > 0:
            ax.annotate(f"{height:,}", (p.get_x() + p.get_width() / 2., height),
                        ha="center", va="bottom", fontsize=10, xytext=(0, 3), textcoords="offset points")
            
    plt.tight_layout()
    fig_path1 = figures_dir / "gsi_records_by_state.png"
    plt.savefig(fig_path1, dpi=300)
    plt.close()
    logger.info(f"Saved figure: {fig_path1}")

    # 2. gsi_missing_values.png
    plt.figure(figsize=(10, 6))
    check_cols = ["slide_id", "state", "district", "slide_name", "road_location", "latitude", "longitude", "material_involved", "movement_type", "history"]
    missing_pct = (df_ner[check_cols].isna().sum() / len(df_ner) * 100).reset_index()
    missing_pct.columns = ["Field", "Missing Percentage"]
    
    ax = sns.barplot(data=missing_pct, x="Field", y="Missing Percentage", palette="magma")
    plt.title("GSI Historical Landslide Inventory — Missing Data Percentage per Field", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Inventory Field", fontsize=12, labelpad=10)
    plt.ylabel("Missing Percentage (%)", fontsize=12, labelpad=10)
    plt.xticks(rotation=45, ha="right")
    plt.ylim(0, 100)
    
    for p in ax.patches:
        val = p.get_height()
        if val > 0:
            ax.annotate(f"{val:.1f}%", (p.get_x() + p.get_width() / 2., val),
                        ha="center", va="bottom", fontsize=9, xytext=(0, 3), textcoords="offset points")
            
    plt.tight_layout()
    fig_path2 = figures_dir / "gsi_missing_values.png"
    plt.savefig(fig_path2, dpi=300)
    plt.close()
    logger.info(f"Saved figure: {fig_path2}")

    # 3. gsi_ner_spatial_distribution.png
    plt.figure(figsize=(10, 8))
    plt.scatter(
        df_ner["lon_num"],
        df_ner["lat_num"],
        c=pd.factorize(df_ner["state_clean"])[0],
        cmap="tab10",
        alpha=0.6,
        s=15,
        edgecolors="none",
    )
    plt.title("GSI Landslide Point Locations — North Eastern Region (EPSG:4326)", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Longitude (°E)", fontsize=12)
    plt.ylabel("Latitude (°N)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    fig_path3 = figures_dir / "gsi_ner_spatial_distribution.png"
    plt.savefig(fig_path3, dpi=300)
    plt.close()
    logger.info(f"Saved figure: {fig_path3}")


def main():
    settings = get_settings()
    logger.info("==================================================")
    logger.info("PHASE 2: GSI HISTORICAL LANDSLIDE INVENTORY PIPELINE")
    logger.info("==================================================")

    pdf_path = settings.GSI_DATA_DIR / "landslide_inventory.pdf"

    # Step 1 & 2: Raw Extraction
    logger.info(f"Step 1 & 2: Extracting raw table records from {pdf_path}")
    df_raw = extract_gsi_pdf_raw(pdf_path=pdf_path, num_workers=4)

    interim_dir = settings.DATA_INTERIM_DIR
    interim_dir.mkdir(parents=True, exist_ok=True)
    raw_interim_csv = interim_dir / "gsi_extracted_raw.csv"
    df_raw.to_csv(raw_interim_csv, index=False)
    logger.info(f"Raw extracted DataFrame saved to {raw_interim_csv} (Shape: {df_raw.shape})")

    # Step 3: Data Cleaning
    logger.info("Step 3: Cleaning strings, filtering headers, and normalizing schema...")
    df_clean = clean_gsi_dataframe(df_raw)

    # Step 4: Coordinate Validation
    logger.info("Step 4: Validating coordinates and adding spatial quality flags...")
    df_validated = validate_coordinates(df_clean)

    # Step 5: NER Filtering
    logger.info("Step 5: Filtering North Eastern Region (NER) landslide records...")
    df_ner, df_non_ner = filter_ner_records(df_validated)

    # Step 6: Data Quality Report
    logger.info("Step 6: Generating reproducible data quality report...")
    quality_report = generate_quality_report(df_raw, df_validated, df_ner, df_non_ner)

    reports_dir = BASE_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / "gsi_data_quality_report.txt"
    report_json = reports_dir / "gsi_data_quality_report.json"

    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, indent=2)

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("==================================================\n")
        f.write("GSI LANDSLIDE INVENTORY — DATA QUALITY REPORT\n")
        f.write("==================================================\n\n")
        for k, v in quality_report.items():
            if isinstance(v, dict):
                f.write(f"\n--- {k} ---\n")
                for sub_k, sub_v in v.items():
                    f.write(f"  {sub_k}: {sub_v}\n")
            else:
                f.write(f"{k}: {v}\n")

    logger.info(f"Quality report written to {report_file}")
    print("\n" + report_file.read_text(encoding="utf-8"))

    # Step 7 & 8: Geospatial Export & Provenance Metadata
    logger.info("Step 7 & 8: Exporting geospatial datasets (CSV, GeoJSON, Parquet, Metadata)...")
    export_paths = export_geospatial_outputs(df_ner, output_dir=settings.DATA_PROCESSED_DIR)

    # Step 9: Exploratory Analysis Figures
    logger.info("Step 9: Generating exploratory analysis figures...")
    figures_dir = reports_dir / "figures"
    generate_figures(df_validated, df_ner, figures_dir)

    logger.info("==================================================")
    logger.info("PHASE 2 PIPELINE EXECUTED SUCCESSFULLY!")
    logger.info("==================================================")


if __name__ == "__main__":
    main()
