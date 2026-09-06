"""SMAP Soil Moisture Processor for NASA SMAP L3 Radiometer Global Daily 36km EASE-Grid Soil Moisture (SPL3SMP).

Discovers SMAP HDF5 files dynamically, resolves duplicate dates by release version,
extracts soil moisture for North-Eastern Region (NER) coordinates, filters fill values (-9999.0),
applies retrieval quality flag policies, and combines AM/PM passes deterministically.
"""

from datetime import date, datetime, timedelta
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

try:
    import h5py
except ImportError:
    h5py = None

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class SMAPProcessor:
    """Processor module for NASA SMAP L3 Radiometer Daily 36km Soil Moisture (SPL3SMP)."""

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        """Initialize the SMAP processor.

        Args:
            data_dir: Path to directory containing SMAP .h5 / .hdf5 files.
                      Defaults to settings.SMAP_DATA_DIR.
        """
        self.settings = get_settings()
        self.data_dir = Path(data_dir or self.settings.SMAP_DATA_DIR)

        self.fill_value = float(self.settings.SMAP_FILL_VALUE)
        self.valid_min = float(self.settings.SMAP_VALID_MIN)
        self.valid_max = float(self.settings.SMAP_VALID_MAX)

        self._date_to_file: Dict[date, Path] = {}
        self._date_to_version: Dict[date, str] = {}
        self._duplicate_dates: set = set()
        self._readable_files: List[Path] = []
        self._corrupt_files: List[Path] = []

        # Caching 2D EASE-Grid geolocation
        self._cached_lats: Optional[np.ndarray] = None
        self._cached_lons: Optional[np.ndarray] = None

        self.discover_files()

    def discover_files(self) -> Dict[date, Path]:
        """Dynamically discover SMAP files, parsing dates and picking highest release versions.

        Returns:
            Dict mapping datetime.date -> Path to the valid SMAP file.
        """
        if not self.data_dir.exists():
            logger.warning(f"SMAP data directory does not exist: {self.data_dir}")
            return {}

        raw_files = sorted(
            list(self.data_dir.glob("*.h5")) + list(self.data_dir.glob("*.hdf5"))
        )

        self._date_to_file.clear()
        self._date_to_version.clear()
        self._duplicate_dates.clear()
        self._readable_files.clear()
        self._corrupt_files.clear()

        for file_path in raw_files:
            file_date, release_ver = self._parse_file_info(file_path.name)
            if file_date is None:
                continue

            if file_date in self._date_to_file:
                self._duplicate_dates.add(file_date)
                # Keep file with higher release version string
                existing_ver = self._date_to_version.get(file_date, "")
                if release_ver > existing_ver:
                    self._date_to_file[file_date] = file_path
                    self._date_to_version[file_date] = release_ver
            else:
                self._date_to_file[file_date] = file_path
                self._date_to_version[file_date] = release_ver

        # Verify readability and cache grid coordinates from first readable file
        for d, fpath in list(self._date_to_file.items()):
            if self._verify_file_readability(fpath):
                self._readable_files.append(fpath)
            else:
                self._corrupt_files.append(fpath)
                logger.error(f"Corrupt or unreadable SMAP file: {fpath}")

        if self._readable_files and self._cached_lats is None:
            self._load_grid_coordinates(self._readable_files[0])

        return self._date_to_file

    def _parse_file_info(self, filename: str) -> Tuple[Optional[date], str]:
        """Parse observation date and release version string from SMAP filename.

        Example: SMAP_L3_SM_P_20190925_R19240_001.h5
        """
        try:
            parts = filename.split("_")
            for i, p in enumerate(parts):
                if len(p) == 8 and p.isdigit():
                    obs_d = datetime.strptime(p, "%Y%m%d").date()
                    version_str = "_".join(parts[i+1:]).split(".")[0]
                    return obs_d, version_str
        except Exception as e:
            logger.debug(f"Failed to parse SMAP file info from {filename}: {e}")
        return None, ""

    def _verify_file_readability(self, file_path: Path) -> bool:
        """Verify HDF5 structure contains required AM/PM retrieval groups."""
        if h5py is None:
            return False
        try:
            with h5py.File(file_path, "r") as h5f:
                return (
                    "Soil_Moisture_Retrieval_Data_AM" in h5f or
                    "Soil_Moisture_Retrieval_Data_PM" in h5f
                )
        except Exception:
            return False

    def _load_grid_coordinates(self, sample_file: Path) -> None:
        """Load and cache 2D EASE-Grid latitude and longitude arrays."""
        if h5py is None:
            return
        try:
            with h5py.File(sample_file, "r") as h5f:
                grp = None
                if "Soil_Moisture_Retrieval_Data_AM" in h5f:
                    grp = h5f["Soil_Moisture_Retrieval_Data_AM"]
                elif "Soil_Moisture_Retrieval_Data_PM" in h5f:
                    grp = h5f["Soil_Moisture_Retrieval_Data_PM"]

                if grp is not None and "latitude" in grp and "longitude" in grp:
                    self._cached_lats = np.array(grp["latitude"][:])
                    self._cached_lons = np.array(grp["longitude"][:])
        except Exception as e:
            logger.error(f"Error loading SMAP grid coordinates from {sample_file}: {e}")

    def get_metadata_summary(self) -> Dict[str, Union[int, float, str, bool, List[str]]]:
        """Generate audit report for SMAP dataset.

        Returns:
            Dictionary containing counts, date range, gaps, and metadata.
        """
        total_files = len(list(self.data_dir.glob("*.h5")) + list(self.data_dir.glob("*.hdf5")))
        total_bytes = sum(f.stat().st_size for f in self.data_dir.glob("*") if f.is_file() and not f.name.startswith("."))

        available_dates = sorted(list(self._date_to_file.keys()))
        earliest_date = available_dates[0].strftime("%Y-%m-%d") if available_dates else None
        latest_date = available_dates[-1].strftime("%Y-%m-%d") if available_dates else None

        missing_dates = []
        if available_dates:
            curr = available_dates[0]
            end_d = available_dates[-1]
            while curr <= end_d:
                if curr not in self._date_to_file:
                    missing_dates.append(curr.strftime("%Y-%m-%d"))
                curr += timedelta(days=1)

        ner_bbox = self.settings.ner_bbox
        ner_covered = False
        lon_min, lon_max, lat_min, lat_max = None, None, None, None

        if self._cached_lats is not None and self._cached_lons is not None:
            lon_min = float(np.min(self._cached_lons))
            lon_max = float(np.max(self._cached_lons))
            lat_min = float(np.min(self._cached_lats))
            lat_max = float(np.max(self._cached_lats))

            ner_covered = (
                lon_min <= ner_bbox[0] and lon_max >= ner_bbox[2] and
                lat_min <= ner_bbox[1] and lat_max >= ner_bbox[3]
            )

        return {
            "total_files_discovered": total_files,
            "readable_file_count": len(self._readable_files),
            "corrupt_file_count": len(self._corrupt_files),
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            "product_name": "SMAP L3 Radiometer Global Daily 36km EASE-Grid Soil Moisture (SPL3SMP)",
            "earliest_date": earliest_date,
            "latest_date": latest_date,
            "available_dates_count": len(available_dates),
            "duplicate_dates_count": len(self._duplicate_dates),
            "missing_dates_count": len(missing_dates),
            "selected_soil_moisture_variable": "soil_moisture (AM) / soil_moisture_pm (PM)",
            "soil_moisture_units": "cm^3/cm^3",
            "fill_value": -9999.0,
            "valid_min": self.valid_min,
            "valid_max": self.valid_max,
            "quality_flag_variable": "retrieval_qual_flag / retrieval_qual_flag_pm",
            "spatial_bounds": {
                "lon_min": lon_min,
                "lon_max": lon_max,
                "lat_min": lat_min,
                "lat_max": lat_max,
            },
            "spatial_resolution": "~36 km EASE-Grid 2.0",
            "ner_covered": ner_covered,
        }

    def _get_nearest_grid_indices(self, lat: float, lon: float) -> Tuple[int, int]:
        """Find the nearest 2D grid row and column indices for a coordinate."""
        if self._cached_lats is None or self._cached_lons is None:
            raise ValueError("SMAP grid coordinates have not been initialized.")

        dist_sq = (self._cached_lats - lat)**2 + (self._cached_lons - lon)**2
        min_idx = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
        return int(min_idx[0]), int(min_idx[1])

    def extract_point(
        self, lat: float, lon: float, obs_date: date, tolerance_days: int = 0
    ) -> Dict[str, Union[float, str, int]]:
        """Extract soil moisture for a single coordinate and date, applying quality flag checks.

        AM/PM Selection Policy:
        1. Reject fill values (-9999.0) and values outside [valid_min, valid_max].
        2. Inspect bit 0 of retrieval_qual_flag (bit 0 = 0 indicates recommended quality).
        3. If both AM and PM are recommended, return average of AM and PM.
        4. If only one is recommended, return that pass.
        5. If both are non-recommended but physically valid, return average with WARNING quality status.
        6. If both are missing/fill, return np.nan with INVALID_RETRIEVAL status.

        Args:
            lat: Target latitude.
            lon: Target longitude.
            obs_date: Target observation date.
            tolerance_days: Maximum allowed date difference (default 0 for strict exact-date match).

        Returns:
            Dict containing soil_moisture, quality, observation_time, source, and status.
        """
        target_file = None
        matched_date = obs_date
        date_offset_days = 0

        if obs_date in self._date_to_file:
            target_file = self._date_to_file[obs_date]
        elif tolerance_days > 0 and self._date_to_file:
            # Nearest date matching within tolerance
            all_dates = np.array(list(self._date_to_file.keys()))
            date_diffs = np.array([abs((d - obs_date).days) for d in all_dates])
            min_idx = int(np.argmin(date_diffs))
            min_diff = int(date_diffs[min_idx])
            if min_diff <= tolerance_days:
                matched_date = all_dates[min_idx]
                target_file = self._date_to_file[matched_date]
                date_offset_days = (matched_date - obs_date).days

        if target_file is None or not target_file.exists():
            return {
                "latitude": lat,
                "longitude": lon,
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "soil_moisture": np.nan,
                "soil_moisture_quality": "INVALID",
                "soil_moisture_observation_time": "N/A",
                "soil_moisture_source": "NO_FILE",
                "soil_moisture_units": "cm^3/cm^3",
                "smap_data_status": "MISSING_FILE",
                "matched_date": None,
                "date_offset_days": 0,
                "source_file": "",
            }

        try:
            row_idx, col_idx = self._get_nearest_grid_indices(lat, lon)
        except ValueError as err:
            return {
                "latitude": lat,
                "longitude": lon,
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "soil_moisture": np.nan,
                "soil_moisture_quality": "INVALID",
                "soil_moisture_observation_time": "N/A",
                "soil_moisture_source": "OUT_OF_BOUNDS",
                "soil_moisture_units": "cm^3/cm^3",
                "smap_data_status": "OUT_OF_BOUNDS",
                "matched_date": None,
                "date_offset_days": 0,
                "source_file": target_file.name,
            }

        try:
            am_sm, am_qf, pm_sm, pm_qf = np.nan, 999, np.nan, 999

            with h5py.File(target_file, "r") as h5f:
                if "Soil_Moisture_Retrieval_Data_AM" in h5f:
                    am_grp = h5f["Soil_Moisture_Retrieval_Data_AM"]
                    if "soil_moisture" in am_grp:
                        am_sm = float(am_grp["soil_moisture"][row_idx, col_idx])
                    if "retrieval_qual_flag" in am_grp:
                        am_qf = int(am_grp["retrieval_qual_flag"][row_idx, col_idx])

                if "Soil_Moisture_Retrieval_Data_PM" in h5f:
                    pm_grp = h5f["Soil_Moisture_Retrieval_Data_PM"]
                    if "soil_moisture_pm" in pm_grp:
                        pm_sm = float(pm_grp["soil_moisture_pm"][row_idx, col_idx])
                    if "retrieval_qual_flag_pm" in pm_grp:
                        pm_qf = int(pm_grp["retrieval_qual_flag_pm"][row_idx, col_idx])

            # Validate physically reasonable soil moisture range
            am_valid = not np.isnan(am_sm) and self.valid_min <= am_sm <= self.valid_max
            pm_valid = not np.isnan(pm_sm) and self.valid_min <= pm_sm <= self.valid_max

            # Bit 0 == 0 indicates recommended retrieval quality
            am_recommended = am_valid and ((am_qf & 1) == 0)
            pm_recommended = pm_valid and ((pm_qf & 1) == 0)

            final_sm = np.nan
            quality_str = "INVALID"
            obs_time_str = "N/A"
            source_str = "INVALID_RETRIEVAL"

            if am_recommended and pm_recommended:
                final_sm = (am_sm + pm_sm) / 2.0
                quality_str = "HIGH"
                obs_time_str = "AM_PM_MEAN"
                source_str = "AM_PM_RECOMMENDED_MEAN"
            elif am_recommended:
                final_sm = am_sm
                quality_str = "RECOMMENDED"
                obs_time_str = "AM_6AM"
                source_str = "AM_RECOMMENDED"
            elif pm_recommended:
                final_sm = pm_sm
                quality_str = "RECOMMENDED"
                obs_time_str = "PM_6PM"
                source_str = "PM_RECOMMENDED"
            elif am_valid and pm_valid:
                final_sm = (am_sm + pm_sm) / 2.0
                quality_str = "WARNING"
                obs_time_str = "AM_PM_MEAN"
                source_str = "AM_PM_NON_RECOMMENDED_MEAN"
            elif am_valid:
                final_sm = am_sm
                quality_str = "WARNING"
                obs_time_str = "AM_6AM"
                source_str = "AM_NON_RECOMMENDED"
            elif pm_valid:
                final_sm = pm_sm
                quality_str = "WARNING"
                obs_time_str = "PM_6PM"
                source_str = "PM_NON_RECOMMENDED"

            status_str = "VALID" if not np.isnan(final_sm) else "INVALID_RETRIEVAL"
            if date_offset_days != 0 and status_str == "VALID":
                status_str = f"NEAREST_DATE_MATCH_OFFSET_{date_offset_days:+}D"

            return {
                "latitude": lat,
                "longitude": lon,
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "soil_moisture": final_sm,
                "soil_moisture_quality": quality_str,
                "soil_moisture_observation_time": obs_time_str,
                "soil_moisture_source": source_str,
                "soil_moisture_units": "cm^3/cm^3",
                "smap_data_status": status_str,
                "matched_date": matched_date.strftime("%Y-%m-%d"),
                "date_offset_days": date_offset_days,
                "source_file": target_file.name,
            }

        except Exception as e:
            return {
                "latitude": lat,
                "longitude": lon,
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "soil_moisture": np.nan,
                "soil_moisture_quality": "INVALID",
                "soil_moisture_observation_time": "N/A",
                "soil_moisture_source": "READ_ERROR",
                "soil_moisture_units": "cm^3/cm^3",
                "smap_data_status": "READ_ERROR",
                "matched_date": None,
                "date_offset_days": 0,
                "source_file": target_file.name,
            }

    def extract_batch(
        self, locations: List[Dict[str, Union[float, str]]], obs_date: date, tolerance_days: int = 0
    ) -> pd.DataFrame:
        """Extract SMAP soil moisture for a batch of locations on a specific date in a single file open context.

        Args:
            locations: List of dicts containing 'latitude' and 'longitude'.
            obs_date: Target observation date.
            tolerance_days: Allowed date matching tolerance.

        Returns:
            pandas DataFrame containing location metadata and extracted SMAP soil moisture features.
        """
        target_file = None
        matched_date = obs_date
        date_offset_days = 0

        if obs_date in self._date_to_file:
            target_file = self._date_to_file[obs_date]
        elif tolerance_days > 0 and self._date_to_file:
            all_dates = np.array(list(self._date_to_file.keys()))
            date_diffs = np.array([abs((d - obs_date).days) for d in all_dates])
            min_idx = int(np.argmin(date_diffs))
            min_diff = int(date_diffs[min_idx])
            if min_diff <= tolerance_days:
                matched_date = all_dates[min_idx]
                target_file = self._date_to_file[matched_date]
                date_offset_days = (matched_date - obs_date).days

        if target_file is None or not target_file.exists():
            records = []
            for loc in locations:
                row = dict(loc)
                row.update({
                    "observation_date": obs_date.strftime("%Y-%m-%d"),
                    "soil_moisture": np.nan,
                    "soil_moisture_quality": "INVALID",
                    "soil_moisture_observation_time": "N/A",
                    "soil_moisture_source": "NO_FILE",
                    "soil_moisture_units": "cm^3/cm^3",
                    "smap_data_status": "MISSING_FILE",
                    "matched_date": None,
                    "date_offset_days": 0,
                    "source_file": "",
                })
                records.append(row)
            return pd.DataFrame(records)

        try:
            am_sm_data, am_qf_data = None, None
            pm_sm_data, pm_qf_data = None, None

            with h5py.File(target_file, "r") as h5f:
                if "Soil_Moisture_Retrieval_Data_AM" in h5f:
                    am_grp = h5f["Soil_Moisture_Retrieval_Data_AM"]
                    if "soil_moisture" in am_grp:
                        am_sm_data = am_grp["soil_moisture"][:]
                    if "retrieval_qual_flag" in am_grp:
                        am_qf_data = am_grp["retrieval_qual_flag"][:]

                if "Soil_Moisture_Retrieval_Data_PM" in h5f:
                    pm_grp = h5f["Soil_Moisture_Retrieval_Data_PM"]
                    if "soil_moisture_pm" in pm_grp:
                        pm_sm_data = pm_grp["soil_moisture_pm"][:]
                    if "retrieval_qual_flag_pm" in pm_grp:
                        pm_qf_data = pm_grp["retrieval_qual_flag_pm"][:]

            records = []
            for loc in locations:
                lat = float(loc["latitude"])
                lon = float(loc["longitude"])

                try:
                    row_idx, col_idx = self._get_nearest_grid_indices(lat, lon)
                    am_sm = float(am_sm_data[row_idx, col_idx]) if am_sm_data is not None else np.nan
                    am_qf = int(am_qf_data[row_idx, col_idx]) if am_qf_data is not None else 999
                    pm_sm = float(pm_sm_data[row_idx, col_idx]) if pm_sm_data is not None else np.nan
                    pm_qf = int(pm_qf_data[row_idx, col_idx]) if pm_qf_data is not None else 999

                    am_valid = not np.isnan(am_sm) and self.valid_min <= am_sm <= self.valid_max
                    pm_valid = not np.isnan(pm_sm) and self.valid_min <= pm_sm <= self.valid_max
                    am_recommended = am_valid and ((am_qf & 1) == 0)
                    pm_recommended = pm_valid and ((pm_qf & 1) == 0)

                    final_sm = np.nan
                    quality_str = "INVALID"
                    obs_time_str = "N/A"
                    source_str = "INVALID_RETRIEVAL"

                    if am_recommended and pm_recommended:
                        final_sm = (am_sm + pm_sm) / 2.0
                        quality_str = "HIGH"
                        obs_time_str = "AM_PM_MEAN"
                        source_str = "AM_PM_RECOMMENDED_MEAN"
                    elif am_recommended:
                        final_sm = am_sm
                        quality_str = "RECOMMENDED"
                        obs_time_str = "AM_6AM"
                        source_str = "AM_RECOMMENDED"
                    elif pm_recommended:
                        final_sm = pm_sm
                        quality_str = "RECOMMENDED"
                        obs_time_str = "PM_6PM"
                        source_str = "PM_RECOMMENDED"
                    elif am_valid and pm_valid:
                        final_sm = (am_sm + pm_sm) / 2.0
                        quality_str = "WARNING"
                        obs_time_str = "AM_PM_MEAN"
                        source_str = "AM_PM_NON_RECOMMENDED_MEAN"
                    elif am_valid:
                        final_sm = am_sm
                        quality_str = "WARNING"
                        obs_time_str = "AM_6AM"
                        source_str = "AM_NON_RECOMMENDED"
                    elif pm_valid:
                        final_sm = pm_sm
                        quality_str = "WARNING"
                        obs_time_str = "PM_6PM"
                        source_str = "PM_NON_RECOMMENDED"

                    status_str = "VALID" if not np.isnan(final_sm) else "INVALID_RETRIEVAL"
                    if date_offset_days != 0 and status_str == "VALID":
                        status_str = f"NEAREST_DATE_MATCH_OFFSET_{date_offset_days:+}D"

                    res = {
                        "latitude": lat,
                        "longitude": lon,
                        "observation_date": obs_date.strftime("%Y-%m-%d"),
                        "soil_moisture": final_sm,
                        "soil_moisture_quality": quality_str,
                        "soil_moisture_observation_time": obs_time_str,
                        "soil_moisture_source": source_str,
                        "soil_moisture_units": "cm^3/cm^3",
                        "smap_data_status": status_str,
                        "matched_date": matched_date.strftime("%Y-%m-%d"),
                        "date_offset_days": date_offset_days,
                        "source_file": target_file.name,
                    }
                except Exception as err:
                    res = {
                        "latitude": lat,
                        "longitude": lon,
                        "observation_date": obs_date.strftime("%Y-%m-%d"),
                        "soil_moisture": np.nan,
                        "soil_moisture_quality": "INVALID",
                        "soil_moisture_observation_time": "N/A",
                        "soil_moisture_source": "OUT_OF_BOUNDS",
                        "soil_moisture_units": "cm^3/cm^3",
                        "smap_data_status": "OUT_OF_BOUNDS",
                        "matched_date": None,
                        "date_offset_days": 0,
                        "source_file": target_file.name,
                    }

                row = dict(loc)
                row.update(res)
                records.append(row)

            return pd.DataFrame(records)

        except Exception as e:
            return pd.DataFrame()
