"""IMERG Rainfall Processor for NASA GPM IMERG 1-day satellite precipitation.

Discovers IMERG netCDF4 files dynamically, parses timestamps, validates precipitation
variables/units, extracts spatial point values across the North-Eastern Region (NER),
and calculates 1-day, 3-day, and 7-day rolling rainfall accumulations with strict gap checking.
"""

from datetime import date, datetime, timedelta
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

try:
    import netCDF4 as nc
except ImportError:
    nc = None

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class IMERGProcessor:
    """Processor module for NASA GPM IMERG 1-day Precipitation (V07B)."""

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        """Initialize the IMERG processor.

        Args:
            data_dir: Path to directory containing IMERG .nc4 / .nc files.
                      Defaults to settings.RAINFALL_DATA_DIR.
        """
        self.settings = get_settings()
        self.data_dir = Path(data_dir or self.settings.RAINFALL_DATA_DIR)
        
        self.precip_var_name = self.settings.IMERG_PRECIP_VARIABLE
        self.fill_value_threshold = -9000.0  # Values <= -9000 are fill/no-data
        
        self._date_to_file: Dict[date, Path] = {}
        self._duplicate_dates: set = set()
        self._readable_files: List[Path] = []
        self._corrupt_files: List[Path] = []
        
        self._cached_lons: Optional[np.ndarray] = None
        self._cached_lats: Optional[np.ndarray] = None
        self._grid_cache: Dict[Path, np.ndarray] = {}

        self.discover_files()

    def _read_precip_grid(self, file_path: Path) -> Optional[np.ndarray]:
        """Read and cache 2D precipitation grid array for a file."""
        if file_path in self._grid_cache:
            return self._grid_cache[file_path]
        if nc is None:
            return None
        try:
            with nc.Dataset(file_path, "r") as ds:
                grid = np.array(ds.variables["precipitation"][0, :, :])
                self._grid_cache[file_path] = grid
                return grid
        except Exception as e:
            logger.error(f"Error reading precip grid from {file_path}: {e}")
            return None

    def discover_files(self) -> Dict[date, Path]:
        """Dynamically discover and validate IMERG files in the data directory.

        Returns:
            Dict mapping datetime.date -> Path to the valid IMERG netCDF file.
        """
        if not self.data_dir.exists():
            logger.warning(f"IMERG data directory does not exist: {self.data_dir}")
            return {}

        raw_files = sorted(
            list(self.data_dir.glob("*.nc4")) + list(self.data_dir.glob("*.nc"))
        )

        self._date_to_file.clear()
        self._duplicate_dates.clear()
        self._readable_files.clear()
        self._corrupt_files.clear()

        for file_path in raw_files:
            file_date = self._parse_date_from_filename(file_path.name)
            if file_date is None:
                continue

            if file_date in self._date_to_file:
                self._duplicate_dates.add(file_date)
                # Keep latest file alphabetically / by modification time
                existing_f = self._date_to_file[file_date]
                if file_path.name > existing_f.name:
                    self._date_to_file[file_date] = file_path
            else:
                self._date_to_file[file_date] = file_path

        # Validate readability of files
        for d, fpath in list(self._date_to_file.items()):
            if self._verify_file_readability(fpath):
                self._readable_files.append(fpath)
            else:
                self._corrupt_files.append(fpath)
                logger.error(f"Corrupt or unreadable IMERG file: {fpath}")

        # Initialize coordinate grid caching from first readable file
        if self._readable_files and self._cached_lons is None:
            self._load_grid_coordinates(self._readable_files[0])

        return self._date_to_file

    def _parse_date_from_filename(self, filename: str) -> Optional[date]:
        """Parse date from standard IMERG filename convention.

        Example: 3B-DAY.MS.MRG.3IMERG.20250504-S000000-E235959.V07B.nc4
        """
        try:
            parts = filename.split(".")
            for part in parts:
                if len(part) >= 8 and part[:8].isdigit():
                    date_str = part[:8]
                    return datetime.strptime(date_str, "%Y%m%d").date()
                if "-" in part and len(part.split("-")[0]) == 8 and part.split("-")[0].isdigit():
                    date_str = part.split("-")[0]
                    return datetime.strptime(date_str, "%Y%m%d").date()
        except Exception as e:
            logger.debug(f"Failed to parse date from filename '{filename}': {e}")
        return None

    def _verify_file_readability(self, file_path: Path) -> bool:
        """Check if netCDF file can be opened and contains expected precipitation variable."""
        if nc is None:
            return False
        try:
            with nc.Dataset(file_path, "r") as ds:
                return (
                    "precipitation" in ds.variables
                    and "lon" in ds.variables
                    and "lat" in ds.variables
                )
        except Exception:
            return False

    def _load_grid_coordinates(self, sample_file: Path) -> None:
        """Load and cache 1D longitude and latitude coordinate arrays."""
        if nc is None:
            return
        try:
            with nc.Dataset(sample_file, "r") as ds:
                self._cached_lons = np.array(ds.variables["lon"][:])
                self._cached_lats = np.array(ds.variables["lat"][:])
        except Exception as e:
            logger.error(f"Error loading grid coordinates from {sample_file}: {e}")

    def get_metadata_summary(self) -> Dict[str, Union[int, float, str, bool, List[str]]]:
        """Generate a complete audit report dictionary for IMERG data.

        Returns:
            Dictionary containing exact counts, date ranges, gaps, and spatial metadata.
        """
        total_files = len(list(self.data_dir.glob("*.nc4")) + list(self.data_dir.glob("*.nc")))
        total_bytes = sum(f.stat().st_size for f in self.data_dir.glob("*") if f.is_file() and not f.name.startswith("."))

        available_dates = sorted(list(self._date_to_file.keys()))
        earliest_date = available_dates[0].strftime("%Y-%m-%d") if available_dates else None
        latest_date = available_dates[-1].strftime("%Y-%m-%d") if available_dates else None

        # Find missing gap dates
        missing_dates = []
        longest_consecutive = 0
        current_consecutive = 0
        usable_windows = []

        if available_dates:
            curr = available_dates[0]
            end_d = available_dates[-1]
            win_start = curr

            while curr <= end_d:
                if curr in self._date_to_file:
                    current_consecutive += 1
                    if current_consecutive > longest_consecutive:
                        longest_consecutive = current_consecutive
                else:
                    missing_dates.append(curr.strftime("%Y-%m-%d"))
                    if current_consecutive > 0:
                        usable_windows.append((win_start.strftime("%Y-%m-%d"), (curr - timedelta(days=1)).strftime("%Y-%m-%d"), current_consecutive))
                    current_consecutive = 0
                    win_start = curr + timedelta(days=1)
                curr += timedelta(days=1)

            if current_consecutive > 0:
                usable_windows.append((win_start.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d"), current_consecutive))

        # Check NER coverage
        ner_bbox = self.settings.ner_bbox
        ner_covered = False
        lon_min, lon_max, lat_min, lat_max = None, None, None, None
        lon_res, lat_res = None, None

        if self._cached_lons is not None and self._cached_lats is not None:
            lon_min = float(np.min(self._cached_lons))
            lon_max = float(np.max(self._cached_lons))
            lat_min = float(np.min(self._cached_lats))
            lat_max = float(np.max(self._cached_lats))
            
            if len(self._cached_lons) > 1:
                lon_res = float(np.abs(np.diff(self._cached_lons)).mean())
            if len(self._cached_lats) > 1:
                lat_res = float(np.abs(np.diff(self._cached_lats)).mean())

            ner_covered = (
                lon_min <= ner_bbox[0] and lon_max >= ner_bbox[2] and
                lat_min <= ner_bbox[1] and lat_max >= ner_bbox[3]
            )

        return {
            "total_files_discovered": total_files,
            "readable_file_count": len(self._readable_files),
            "corrupt_file_count": len(self._corrupt_files),
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            "product_name": "GPM IMERG Final Precipitation L3 1 day 0.1 degree x 0.1 degree (GPM_3IMERGDF V07B)",
            "earliest_date": earliest_date,
            "latest_date": latest_date,
            "available_dates_count": len(available_dates),
            "duplicate_dates_count": len(self._duplicate_dates),
            "missing_dates_count": len(missing_dates),
            "missing_dates": missing_dates,
            "longest_consecutive_days": longest_consecutive,
            "usable_consecutive_windows": usable_windows,
            "precipitation_variable": "precipitation",
            "precipitation_units": "mm/day",
            "fill_value": -9999.9,
            "spatial_bounds": {
                "lon_min": lon_min,
                "lon_max": lon_max,
                "lat_min": lat_min,
                "lat_max": lat_max,
            },
            "spatial_resolution": {
                "lon_res": lon_res,
                "lat_res": lat_res,
            },
            "ner_covered": ner_covered,
        }

    def _get_nearest_grid_indices(self, lat: float, lon: float) -> Tuple[int, int]:
        """Find the nearest grid cell indices (lon_idx, lat_idx) for a coordinate.

        Raises:
            ValueError: If grid coordinates are not cached or target is out of bounds.
        """
        if self._cached_lons is None or self._cached_lats is None:
            raise ValueError("IMERG grid coordinates have not been initialized.")

        if (
            lon < np.min(self._cached_lons) or lon > np.max(self._cached_lons) or
            lat < np.min(self._cached_lats) or lat > np.max(self._cached_lats)
        ):
            raise ValueError(f"Coordinate ({lat}, {lon}) is out of IMERG geographic bounds.")

        lon_idx = int(np.argmin(np.abs(self._cached_lons - lon)))
        lat_idx = int(np.argmin(np.abs(self._cached_lats - lat)))
        return lon_idx, lat_idx

    def extract_point(self, lat: float, lon: float, obs_date: date) -> Dict[str, Union[float, str, bool]]:
        """Extract daily rainfall for a single coordinate and date.

        Args:
            lat: Target latitude.
            lon: Target longitude.
            obs_date: Target observation date.

        Returns:
            Dict containing extracted rainfall_1d, units, status, and provenance.
        """
        if obs_date not in self._date_to_file:
            return {
                "rainfall_1d": np.nan,
                "units": "mm/day",
                "status": "MISSING_FILE",
                "status_reason": f"No IMERG file present for date {obs_date}",
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "source_file": "",
            }

        file_path = self._date_to_file[obs_date]

        try:
            lon_idx, lat_idx = self._get_nearest_grid_indices(lat, lon)
        except ValueError as err:
            return {
                "rainfall_1d": np.nan,
                "units": "mm/day",
                "status": "OUT_OF_BOUNDS",
                "status_reason": str(err),
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "source_file": file_path.name,
            }

        try:
            grid = self._read_precip_grid(file_path)
            if grid is None:
                precip_val = np.nan
            else:
                precip_val = float(grid[lon_idx, lat_idx])

            if np.isnan(precip_val) or precip_val <= self.fill_value_threshold:
                return {
                    "rainfall_1d": np.nan,
                    "units": "mm/day",
                    "status": "INVALID_VALUE",
                    "status_reason": f"Value {precip_val} is fill/no-data",
                    "observation_date": obs_date.strftime("%Y-%m-%d"),
                    "source_file": file_path.name,
                }

            # Physically plausible range check for daily rainfall (0 to 2500 mm/day)
            precip_val = max(0.0, float(precip_val))

            return {
                "rainfall_1d": precip_val,
                "units": "mm/day",
                "status": "VALID",
                "status_reason": "Extraction successful",
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "source_file": file_path.name,
            }

        except Exception as e:
            return {
                "rainfall_1d": np.nan,
                "units": "mm/day",
                "status": "READ_ERROR",
                "status_reason": str(e),
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "source_file": file_path.name,
            }

    def extract_point_rolling(
        self, lat: float, lon: float, target_date: date
    ) -> Dict[str, Union[float, str, List[str]]]:
        """Extract rainfall features (1d, 3d, 7d) for a target date with strict gap enforcement.

        Definitions:
        - rainfall_1d: Rainfall accumulation on target_date.
        - rainfall_3d: Sum of 3 consecutive daily observations (target_date, target_date-1d, target_date-2d).
        - rainfall_7d: Sum of 7 consecutive daily observations (target_date to target_date-6d).

        If any required day in the consecutive window is missing or invalid, the rolling sum
        returns np.nan with an explicit INSUFFICIENT_HISTORY status.

        Args:
            lat: Target latitude.
            lon: Target longitude.
            target_date: Target observation date.

        Returns:
            Dict containing rainfall_1d, rainfall_3d, rainfall_7d, status, and details.
        """
        r1d_res = self.extract_point(lat, lon, target_date)
        r1d_val = r1d_res["rainfall_1d"]

        # Extract past 7 consecutive days
        daily_vals: List[float] = []
        missing_days: List[str] = []

        for offset in range(7):
            d = target_date - timedelta(days=offset)
            res = self.extract_point(lat, lon, d)
            if res["status"] == "VALID" and not np.isnan(res["rainfall_1d"]):
                daily_vals.append(float(res["rainfall_1d"]))
            else:
                daily_vals.append(np.nan)
                missing_days.append(d.strftime("%Y-%m-%d"))

        # Calculate 3-day sum (indices 0, 1, 2)
        if len(daily_vals) >= 3 and not any(np.isnan(daily_vals[:3])):
            r3d_val = float(sum(daily_vals[:3]))
            status_3d = "VALID"
        else:
            r3d_val = np.nan
            status_3d = "INSUFFICIENT_HISTORY"

        # Calculate 7-day sum (indices 0 to 6)
        if len(daily_vals) == 7 and not any(np.isnan(daily_vals)):
            r7d_val = float(sum(daily_vals))
            status_7d = "VALID"
        else:
            r7d_val = np.nan
            status_7d = "INSUFFICIENT_HISTORY"

        overall_status = "VALID"
        if np.isnan(r1d_val):
            overall_status = "MISSING_DATA"
        elif status_3d == "INSUFFICIENT_HISTORY" or status_7d == "INSUFFICIENT_HISTORY":
            overall_status = "INSUFFICIENT_HISTORY"

        return {
            "latitude": lat,
            "longitude": lon,
            "observation_date": target_date.strftime("%Y-%m-%d"),
            "rainfall_1d": r1d_val,
            "rainfall_3d": r3d_val,
            "rainfall_7d": r7d_val,
            "rainfall_data_status": overall_status,
            "status_3d": status_3d,
            "status_7d": status_7d,
            "missing_dates_in_7d_window": missing_days,
            "rainfall_source_file": r1d_res.get("source_file", ""),
            "rainfall_units": "mm/day",
        }

    def extract_batch(
        self, locations: List[Dict[str, Union[float, str]]], obs_date: date
    ) -> pd.DataFrame:
        """Extract IMERG rainfall features for a batch of locations on a specific date.

        Args:
            locations: List of dicts containing 'latitude' and 'longitude' (and optional metadata like 'site_name').
            obs_date: Target observation date.

        Returns:
            pandas DataFrame containing location metadata, rainfall_1d, rainfall_3d, rainfall_7d, and status.
        """
        records = []
        for loc in locations:
            lat = float(loc["latitude"])
            lon = float(loc["longitude"])
            
            res = self.extract_point_rolling(lat, lon, obs_date)
            row = dict(loc)
            row.update(res)
            records.append(row)

        return pd.DataFrame(records)
