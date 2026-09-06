"""SRTM Digital Elevation Model (DEM) Loader.

Responsible for discovering, safely extracting, parsing metadata,
and indexing SRTM DEM elevation tiles for the North-Eastern Region (NER) of India.
"""

from pathlib import Path
import re
import math
import zipfile
import struct
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from src.config.settings import get_settings

settings = get_settings()

# Standard SRTMGL1 resolution: 1 arc-second = 3601 x 3601 pixels
SRTMGL1_DIM = 3601
SRTMGL1_BYTE_SIZE = SRTMGL1_DIM * SRTMGL1_DIM * 2  # 12,967,201 bytes (big-endian int16)
NODATA_VALUE = -32768


def parse_tile_bounds(filename: str) -> Dict[str, Any]:
    """Parse geographic bounding box and corner coordinates from SRTM tile filename.

    Example filenames: 'N20E087.SRTMGL1.hgt.zip', 'N20E087.hgt', 'S12W045'

    Parameters
    ----------
    filename : str
        Filename or tile identifier string.

    Returns
    -------
    Dict[str, Any]
        Dictionary with south_lat, north_lat, west_lon, east_lon, tile_id.
    """
    stem = Path(filename).name
    # Match standard SRTM pattern e.g., N20E087 or S05W070
    match = re.search(r"([NS])(\d{2})([EW])(\d{3})", stem, re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not parse valid SRTM coordinates from filename: '{filename}'")

    lat_dir, lat_str, lon_dir, lon_str = match.groups()

    south_lat = float(lat_str) * (-1.0 if lat_dir.upper() == "S" else 1.0)
    west_lon = float(lon_str) * (-1.0 if lon_dir.upper() == "W" else 1.0)

    north_lat = south_lat + 1.0
    east_lon = west_lon + 1.0

    tile_id = f"{lat_dir.upper()}{int(lat_str):02d}{lon_dir.upper()}{int(lon_str):03d}"

    return {
        "tile_id": tile_id,
        "south_lat": south_lat,
        "north_lat": north_lat,
        "west_lon": west_lon,
        "east_lon": east_lon,
        "expected_hgt": f"{tile_id}.hgt",
    }


def discover_srtm_archives(dem_dir: Optional[Path] = None) -> List[Path]:
    """Discover all SRTM *.hgt.zip archives in the raw DEM directory.

    Parameters
    ----------
    dem_dir : Optional[Path]
        Directory to search. Defaults to settings.DEM_DATA_DIR.

    Returns
    -------
    List[Path]
        List of paths to *.hgt.zip files sorted by filename.
    """
    target_dir = dem_dir or settings.DEM_DATA_DIR
    if not target_dir.exists():
        raise FileNotFoundError(f"DEM directory '{target_dir}' does not exist.")

    archives = list(target_dir.glob("*.hgt.zip")) + list(target_dir.glob("*.SRTMGL1.hgt.zip"))
    # Remove duplicates if glob patterns overlap
    unique_archives = sorted(list(set(archives)))
    return unique_archives


def safe_extract_archive(
    zip_path: Path, output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Safely extract the .hgt member from an SRTM zip archive into output_dir.

    Implements safe zip extraction (Zip-Slip protection) and reuses existing valid
    extracted files to prevent unnecessary re-decompression.

    Parameters
    ----------
    zip_path : Path
        Path to the *.hgt.zip archive.
    output_dir : Optional[Path]
        Destination directory. Defaults to settings.DATA_INTERIM_DIR / "dem_extracted".

    Returns
    -------
    Dict[str, Any]
        Extraction status audit dictionary.
    """
    target_dir = output_dir or (settings.DATA_INTERIM_DIR / "dem_extracted")
    target_dir.mkdir(parents=True, exist_ok=True)

    archive_size = zip_path.stat().st_size
    info = parse_tile_bounds(zip_path.name)
    expected_hgt_name = info["expected_hgt"]
    extracted_path = target_dir / expected_hgt_name

    audit = {
        "archive_filename": zip_path.name,
        "tile_id": info["tile_id"],
        "expected_hgt": expected_hgt_name,
        "archive_size_bytes": archive_size,
        "south_lat": info["south_lat"],
        "north_lat": info["north_lat"],
        "west_lon": info["west_lon"],
        "east_lon": info["east_lon"],
        "zip_valid": False,
        "hgt_member_found": False,
        "extraction_status": "pending",
        "extracted_path": str(extracted_path),
        "error_message": "",
    }

    # Reuse existing extracted file if valid
    if extracted_path.exists():
        file_size = extracted_path.stat().st_size
        if file_size == SRTMGL1_BYTE_SIZE:
            audit["zip_valid"] = True
            audit["hgt_member_found"] = True
            audit["extraction_status"] = "reused_cached"
            return audit
        else:
            # Corrupt/incomplete extracted file, remove and re-extract
            extracted_path.unlink()

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            audit["zip_valid"] = True
            hgt_member = None

            for member in zf.infolist():
                member_path = Path(member.filename)
                # Security Check: Prevent Zip-Slip path traversal
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ValueError(f"Path traversal detected in zip member: '{member.filename}'")

                if member.filename.lower().endswith(".hgt"):
                    hgt_member = member
                    break

            if hgt_member is None:
                audit["error_message"] = "No .hgt member found in zip archive."
                audit["extraction_status"] = "failed_missing_hgt"
                return audit

            audit["hgt_member_found"] = True

            # Extract directly to target file name
            with zf.open(hgt_member) as source, open(extracted_path, "wb") as target:
                target.write(source.read())

            extracted_size = extracted_path.stat().st_size
            if extracted_size != SRTMGL1_BYTE_SIZE:
                audit["extraction_status"] = "extracted_non_standard_size"
                audit["error_message"] = f"Extracted size {extracted_size} != expected {SRTMGL1_BYTE_SIZE}"
            else:
                audit["extraction_status"] = "extracted_success"

    except zipfile.BadZipFile as e:
        audit["zip_valid"] = False
        audit["extraction_status"] = "corrupt_zip"
        audit["error_message"] = str(e)
    except Exception as e:
        audit["extraction_status"] = "failed_exception"
        audit["error_message"] = str(e)

    return audit


class SRTMTileIndex:
    """Memory-efficient spatial index for SRTM DEM tiles."""

    def __init__(self):
        self.tiles: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self.extracted_dir: Optional[Path] = None

    def add_tile(self, info: Dict[str, Any], hgt_path: Path):
        """Add an extracted HGT tile to the spatial index.

        Keyed by (int(south_lat), int(west_lon)).
        """
        south_key = int(math.floor(info["south_lat"]))
        west_key = int(math.floor(info["west_lon"]))
        
        self.tiles[(south_key, west_key)] = {
            "tile_id": info["tile_id"],
            "south_lat": info["south_lat"],
            "north_lat": info["north_lat"],
            "west_lon": info["west_lon"],
            "east_lon": info["east_lon"],
            "hgt_path": hgt_path,
        }

    def find_tile(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Lookup the SRTM tile containing the given (lat, lon) coordinate.

        Parameters
        ----------
        lat : float
            Latitude in degrees North.
        lon : float
            Longitude in degrees East.

        Returns
        -------
        Optional[Dict[str, Any]]
            Tile metadata dictionary or None if out of bounds / missing tile.
        """
        if np.isnan(lat) or np.isnan(lon):
            return None

        south_key = int(math.floor(lat))
        west_key = int(math.floor(lon))

        tile = self.tiles.get((south_key, west_key))
        if tile is None:
            return None

        # Verify strict bounding box check (south <= lat <= north, west <= lon <= east)
        if (tile["south_lat"] <= lat <= tile["north_lat"]) and (tile["west_lon"] <= lon <= tile["east_lon"]):
            return tile

        return None


def read_hgt_raster(hgt_path: Path) -> np.ndarray:
    """Read a standard SRTMGL1 .hgt binary file into a 2D numpy array.

    SRTMGL1 tiles are 3601 x 3601 big-endian signed 16-bit integers (>i2).

    Parameters
    ----------
    hgt_path : Path
        Path to the extracted .hgt file.

    Returns
    -------
    np.ndarray
        2D numpy array of shape (3601, 3601) with dtype int16.
    """
    file_size = hgt_path.stat().st_size
    if file_size == SRTMGL1_BYTE_SIZE:
        dim = SRTMGL1_DIM
    else:
        # Calculate dimension dynamically for non-standard tiles e.g. 1201 x 1201 (SRTM3)
        dim = int(math.sqrt(file_size // 2))
        if dim * dim * 2 != file_size:
            raise ValueError(f"File size {file_size} of {hgt_path} does not match expected HGT structure.")

    with open(hgt_path, "rb") as f:
        # SRTM files are stored in big-endian byte order
        data = np.fromfile(f, dtype=">i2", count=dim * dim)

    return data.reshape((dim, dim))
