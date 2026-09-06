"""GSI (Geological Survey of India) Historical Landslide Inventory Loader.

Provides reproducible pipeline functions to extract raw table records from the GSI
historical landslide inventory PDF, clean and normalize attributes, validate coordinates,
filter North-Eastern Region (NER) records, generate data-quality reports, and export
geospatial vector outputs.
"""

from concurrent.futures import ProcessPoolExecutor
import json
import logging
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple, Union

try:
    import geopandas as gpd
except ImportError:
    gpd = None

import numpy as np
import pandas as pd

try:
    import pymupdf
except ImportError:
    pymupdf = None

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# Target schema definition
CANONICAL_COLUMNS = [
    "sl_no",
    "slide_id",
    "state",
    "district",
    "slide_name",
    "road_location",
    "latitude",
    "longitude",
    "material_involved",
    "movement_type",
    "history",
]

# Official North-Eastern Region (NER) Target States
NER_TARGET_STATES = [
    "Arunachal Pradesh",
    "Assam",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Sikkim",
    "Tripura",
]


def _process_page_chunk(pdf_path_str: str, start_page: int, end_page: int) -> List[Tuple[int, List[str]]]:
    """Helper worker to extract raw table rows from a range of pages in the PDF."""
    doc = pymupdf.open(pdf_path_str)
    records = []
    for page_idx in range(start_page, end_page):
        page = doc[page_idx]
        tabs = page.find_tables()
        if tabs and tabs.tables:
            for t in tabs.tables:
                extracted = t.extract()
                for row in extracted:
                    if row and any(row):
                        records.append((page_idx + 1, list(row)))
    doc.close()
    return records


def extract_gsi_pdf_raw(
    pdf_path: Optional[Path] = None,
    num_workers: int = 4,
) -> pd.DataFrame:
    """Extract raw table records from GSI landslide inventory PDF.

    Parameters
    ----------
    pdf_path : Optional[Path]
        Path to the PDF file. Defaults to `data/raw/gsi/landslide_inventory.pdf`.
    num_workers : int
        Number of parallel workers for page parsing.

    Returns
    -------
    pd.DataFrame
        Raw extracted DataFrame with original strings and `page_num`.
    """
    settings = get_settings()
    target_path = pdf_path or (settings.GSI_DATA_DIR / "landslide_inventory.pdf")

    if not target_path.exists():
        raise FileNotFoundError(
            f"GSI inventory PDF not found at '{target_path}'. "
            "Please place landslide_inventory.pdf in data/raw/gsi/"
        )

    logger.info(f"Opening GSI inventory PDF at: {target_path}")
    doc = pymupdf.open(str(target_path))
    total_pages = len(doc)
    doc.close()

    logger.info(f"Total pages in PDF: {total_pages}. Processing with {num_workers} worker(s)...")

    if num_workers > 1 and total_pages > 10:
        chunk_size = (total_pages + num_workers - 1) // num_workers
        ranges = [
            (i * chunk_size, min((i + 1) * chunk_size, total_pages))
            for i in range(num_workers)
        ]
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(_process_page_chunk, str(target_path), r[0], r[1])
                for r in ranges
            ]
            results = [f.result() for f in futures]
        raw_rows = [row for res in results for row in res]
    else:
        raw_rows = _process_page_chunk(str(target_path), 0, total_pages)

    logger.info(f"Extracted {len(raw_rows)} raw row tuples from {total_pages} pages.")

    # Flatten page_num and table columns
    records = []
    for page_num, r in raw_rows:
        # Pad row to at least 11 elements if truncated
        row_padded = r + [None] * max(0, 11 - len(r))
        records.append([page_num] + row_padded[:11])

    cols = ["page_num"] + CANONICAL_COLUMNS
    df_raw = pd.DataFrame(records, columns=cols)
    return df_raw


def normalize_state_name(val: Optional[str]) -> Optional[str]:
    """Clean and map state strings to canonical NER state names if matched."""
    if not val or not isinstance(val, str):
        return None
    
    clean = val.strip().strip("-").strip()
    if not clean:
        return None
    
    clean_upper = clean.upper()
    
    state_mapping = {
        "ARUNACHAL PRADESH": "Arunachal Pradesh",
        "ARUNACHALPRADESH": "Arunachal Pradesh",
        "ARUNACHAL": "Arunachal Pradesh",
        "ASSAM": "Assam",
        "ASAM": "Assam",
        "MANIPUR": "Manipur",
        "MEGHALAYA": "Meghalaya",
        "MEGHALAY": "Meghalaya",
        "MIZORAM": "Mizoram",
        "NAGALAND": "Nagaland",
        "SIKKIM": "Sikkim",
        "TRIPURA": "Tripura",
    }
    
    for key, val_mapped in state_mapping.items():
        if clean_upper == key or clean_upper.startswith(key):
            return val_mapped

    return clean.title()


def clean_gsi_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Clean, filter header artifacts, and normalize GSI raw dataframe columns.

    Parameters
    ----------
    df_raw : pd.DataFrame
        Raw dataframe extracted from PDF.

    Returns
    -------
    pd.DataFrame
        Cleaned dataframe with canonical schema.
    """
    df = df_raw.copy()

    # Clean strings across all object columns
    for col in CANONICAL_COLUMNS:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .replace([r"^\s*$", r"^None$", r"^nan$", r"^NaN$", r"^N/A$", r"^NA$"], np.nan, regex=True)
            )
            # Remove newline characters and collapse repeated spaces
            df[col] = df[col].apply(
                lambda x: re.sub(r"\s+", " ", str(x).replace("\n", " ")).strip()
                if pd.notna(x) and x != "nan"
                else np.nan
            )

    # Filter out header rows and repeated page headers
    header_keywords = [
        "LANDSLIDE INVENTORY",
        "Sl.No.",
        "Slide_No",
        "State",
        "District",
        "Latitude",
    ]
    
    is_header = df["sl_no"].astype(str).str.contains("|".join(header_keywords), case=False, na=False) | \
                df["state"].astype(str).str.contains("^State$", case=False, na=False) | \
                df["latitude"].astype(str).str.contains("^Latitude$", case=False, na=False)

    df_clean = df[~is_header].copy().reset_index(drop=True)

    # Normalize state field
    df_clean["state_clean"] = df_clean["state"].apply(normalize_state_name)

    return df_clean


def parse_coordinate(val: Union[str, float, int, None]) -> Optional[float]:
    """Parse lat/lon string to float degree value."""
    if pd.isna(val) or val is None:
        return np.nan
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ["na", "n/a", "none", "nan", "null"]:
        return np.nan
    
    # Try direct float conversion first
    try:
        return float(val_str)
    except ValueError:
        pass
    
    # Extract numeric pattern (handling DMS or trailing noise e.g., 25° 30' 15" N or 25.456 N)
    match = re.search(r"(\d{1,3}(?:\.\d+)?)", val_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return np.nan
            
    return np.nan


def validate_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Validate latitude and longitude columns and attach validation flags.

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned GSI dataframe.

    Returns
    -------
    pd.DataFrame
        Dataframe with added coordinate numeric columns and validation flag columns.
    """
    settings = get_settings()
    df_val = df.copy()

    df_val["lat_num"] = df_val["latitude"].apply(parse_coordinate)
    df_val["lon_num"] = df_val["longitude"].apply(parse_coordinate)

    # Flag definitions
    df_val["coord_missing"] = df_val["lat_num"].isna() | df_val["lon_num"].isna()
    
    # Swapped coordinates check (in India, Lat is ~6-38°N, Lon is ~68-98°E. If Lat > 60 and Lon < 35, swapped!)
    df_val["coord_swapped"] = (
        (df_val["lat_num"] > 60.0) & (df_val["lon_num"] < 38.0)
    )

    # Fix swapped coordinates internally for validation evaluation
    actual_lat = np.where(df_val["coord_swapped"], df_val["lon_num"], df_val["lat_num"])
    actual_lon = np.where(df_val["coord_swapped"], df_val["lat_num"], df_val["lon_num"])

    df_val["coord_impossible"] = (
        (actual_lat < -90.0) | (actual_lat > 90.0) |
        (actual_lon < -180.0) | (actual_lon > 180.0)
    )

    # Outside India bounding box check (Lat: 6-38, Lon: 68-98)
    df_val["outside_india"] = (
        ~df_val["coord_missing"] &
        ~df_val["coord_impossible"] &
        ((actual_lat < 6.0) | (actual_lat > 38.0) | (actual_lon < 68.0) | (actual_lon > 98.0))
    )

    # Outside NER bounding box check
    min_lon, min_lat, max_lon, max_lat = settings.ner_bbox
    df_val["outside_ner_bbox"] = (
        ~df_val["coord_missing"] &
        ~df_val["coord_impossible"] &
        ((actual_lat < min_lat) | (actual_lat > max_lat) | (actual_lon < min_lon) | (actual_lon > max_lon))
    )

    # Valid coordinate flag: non-missing, non-impossible, inside India
    df_val["is_valid_coord"] = (
        ~df_val["coord_missing"] &
        ~df_val["coord_impossible"] &
        ~df_val["outside_india"]
    )

    return df_val


def filter_ner_records(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Filter records belonging to the North-Eastern Region (NER).

    Matches records where `state_clean` is in `NER_TARGET_STATES` AND coordinates are valid.

    Parameters
    ----------
    df : pd.DataFrame
        Dataframe with cleaned states and validated coordinates.

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame]
        (df_ner, df_non_ner)
    """
    is_ner_state = df["state_clean"].isin(NER_TARGET_STATES)
    is_ner_record = is_ner_state & df["is_valid_coord"] & (~df["outside_ner_bbox"])

    df_ner = df[is_ner_record].copy().reset_index(drop=True)
    df_non_ner = df[~is_ner_record].copy().reset_index(drop=True)

    return df_ner, df_non_ner


def generate_quality_report(
    df_raw: pd.DataFrame,
    df_clean: pd.DataFrame,
    df_ner: pd.DataFrame,
    df_non_ner: pd.DataFrame,
) -> Dict:
    """Generate comprehensive reproducible data-quality metrics dictionary."""
    total_raw = len(df_raw)
    headers_removed = total_raw - len(df_clean)
    total_parsed = len(df_clean)
    ner_records_count = len(df_ner)
    non_ner_count = len(df_non_ner)

    missing_coords = int(df_clean["coord_missing"].sum())
    impossible_coords = int(df_clean["coord_impossible"].sum())
    swapped_coords = int(df_clean["coord_swapped"].sum())
    outside_india = int(df_clean["outside_india"].sum())
    outside_ner_bbox = int(df_clean["outside_ner_bbox"].sum())

    missing_state = int(df_clean["state_clean"].isna().sum())
    missing_district = int(df_clean["district"].isna().sum())

    # Duplicate candidates check (exact slide_id or lat/lon duplicates)
    duplicate_slide_ids = int(df_clean.duplicated(subset=["slide_id"], keep=False).sum())
    duplicate_coords = int(
        df_clean[~df_clean["coord_missing"]].duplicated(subset=["lat_num", "lon_num"], keep=False).sum()
    )

    state_counts = df_ner["state_clean"].value_counts().to_dict()
    district_counts = df_ner["district"].value_counts().head(20).to_dict()
    material_counts = df_ner["material_involved"].value_counts().to_dict()
    movement_counts = df_ner["movement_type"].value_counts().to_dict()

    report = {
        "total_extracted_rows": total_raw,
        "header_rows_removed": headers_removed,
        "total_parsed_rows": total_parsed,
        "ner_records_count": ner_records_count,
        "non_ner_records_count": non_ner_count,
        "missing_coordinates_count": missing_coords,
        "impossible_coordinates_count": impossible_coords,
        "swapped_coordinates_count": swapped_coords,
        "outside_india_count": outside_india,
        "outside_ner_bbox_count": outside_ner_bbox,
        "missing_state_count": missing_state,
        "missing_district_count": missing_district,
        "duplicate_slide_id_count": duplicate_slide_ids,
        "duplicate_coord_count": duplicate_coords,
        "counts_by_state": state_counts,
        "counts_by_district_top20": district_counts,
        "material_type_distribution": material_counts,
        "movement_type_distribution": movement_counts,
    }

    return report


def export_geospatial_outputs(
    df_ner: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> Dict[str, Path]:
    """Create GeoDataFrame and export CSV, GeoJSON, Parquet, and metadata files.

    Parameters
    ----------
    df_ner : pd.DataFrame
        Filtered NER landslide dataframe.
    output_dir : Optional[Path]
        Target directory for processed outputs. Defaults to `data/processed`.

    Returns
    -------
    Dict[str, Path]
        Dictionary of generated file paths.
    """
    settings = get_settings()
    target_dir = output_dir or settings.DATA_PROCESSED_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    df_export = df_ner.copy()
    
    # Ensure correct lat/lon numeric columns for geometry
    gdf = gpd.GeoDataFrame(
        df_export,
        geometry=gpd.points_from_xy(df_export["lon_num"], df_export["lat_num"]),
        crs=settings.CRS_GEOGRAPHIC,
    )

    csv_path = target_dir / "gsi_landslides_ner.csv"
    geojson_path = target_dir / "gsi_landslides_ner.geojson"
    parquet_path = target_dir / "gsi_landslides_ner.parquet"
    metadata_path = target_dir / "gsi_landslides_ner_metadata.json"

    # Export CSV
    df_export.to_csv(csv_path, index=False)
    logger.info(f"Exported CSV: {csv_path}")

    # Export GeoJSON
    gdf.to_file(geojson_path, driver="GeoJSON")
    logger.info(f"Exported GeoJSON: {geojson_path}")

    # Export Parquet if pyarrow/geoparquet available
    try:
        gdf.to_parquet(parquet_path)
        logger.info(f"Exported Parquet: {parquet_path}")
    except Exception as e:
        logger.warning(f"Parquet export failed (optional): {e}")
        parquet_path = None

    # Export Metadata JSON
    metadata = {
        "dataset_name": "GSI Historical Landslide Inventory — North Eastern Region (NER)",
        "source": "Geological Survey of India (GSI) Historical Landslide Inventory PDF",
        "crs": settings.CRS_GEOGRAPHIC,
        "record_count": len(gdf),
        "columns": list(gdf.columns),
        "ner_states": NER_TARGET_STATES,
        "bounding_box": settings.ner_bbox,
        "processing_pipeline": "PDF Table Extraction -> String Cleaning -> Coordinate Parsing/Validation -> State Normalization -> Geospatial Export",
        "scientific_note": "Records represent historical positive landslide location observations. History dates are preserved where present but no event dates or IMERG rainfall linkages have been fabricated.",
    }
    
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Exported Metadata JSON: {metadata_path}")

    return {
        "csv": csv_path,
        "geojson": geojson_path,
        "parquet": parquet_path,
        "metadata": metadata_path,
    }
