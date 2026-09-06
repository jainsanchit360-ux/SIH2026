"""Temporal Alignment module for aligning IMERG rainfall features and SMAP soil moisture observations.

Combines satellite environmental data streams into a single temporally aligned record per
location and date, preserving source provenance, missing data flags, and alignment statuses.
"""

from datetime import date
import logging
from typing import Dict, List, Optional, Union
import numpy as np
import pandas as pd

from src.data.processors.imerg_processor import IMERGProcessor
from src.data.processors.smap_processor import SMAPProcessor

logger = logging.getLogger(__name__)


class TemporalAligner:
    """Combines IMERG rainfall features and SMAP soil moisture observations into unified records."""

    def __init__(
        self,
        imerg_processor: Optional[IMERGProcessor] = None,
        smap_processor: Optional[SMAPProcessor] = None,
    ):
        """Initialize aligner with processors.

        Args:
            imerg_processor: Instance of IMERGProcessor.
            smap_processor: Instance of SMAPProcessor.
        """
        self.imerg_proc = imerg_processor or IMERGProcessor()
        self.smap_proc = smap_processor or SMAPProcessor()

    def align_observation(
        self, lat: float, lon: float, obs_date: date, smap_tolerance_days: int = 0
    ) -> Dict[str, Union[float, str, int]]:
        """Align IMERG rainfall and SMAP soil moisture for a single location and date.

        Args:
            lat: Latitude.
            lon: Longitude.
            obs_date: Target observation date.
            smap_tolerance_days: Allowed SMAP date matching tolerance.

        Returns:
            Dict containing aligned environmental feature record.
        """
        # Extract IMERG features
        rain_rec = self.imerg_proc.extract_point_rolling(lat, lon, obs_date)
        
        # Extract SMAP features
        smap_rec = self.smap_proc.extract_point(lat, lon, obs_date, tolerance_days=smap_tolerance_days)

        r1d = rain_rec["rainfall_1d"]
        r3d = rain_rec["rainfall_3d"]
        r7d = rain_rec["rainfall_7d"]
        r_status = rain_rec["rainfall_data_status"]

        sm = smap_rec["soil_moisture"]
        sm_status = smap_rec["smap_data_status"]

        # Determine overall alignment completeness status
        r_valid = not np.isnan(r1d)
        sm_valid = not np.isnan(sm)

        if r_valid and sm_valid:
            overall_status = "COMPLETE"
        elif r_valid:
            overall_status = "PARTIAL_RAINFALL_ONLY"
        elif sm_valid:
            overall_status = "PARTIAL_SOIL_MOISTURE_ONLY"
        else:
            overall_status = "INSUFFICIENT_DATA"

        return {
            "latitude": lat,
            "longitude": lon,
            "observation_date": obs_date.strftime("%Y-%m-%d"),
            "rainfall_1d": r1d,
            "rainfall_3d": r3d,
            "rainfall_7d": r7d,
            "soil_moisture": sm,
            "soil_moisture_quality": smap_rec["soil_moisture_quality"],
            "soil_moisture_observation_time": smap_rec["soil_moisture_observation_time"],
            "soil_moisture_source": smap_rec["soil_moisture_source"],
            "rainfall_data_status": r_status,
            "soil_moisture_data_status": sm_status,
            "overall_alignment_status": overall_status,
            "smap_matched_date": smap_rec.get("matched_date"),
            "smap_date_offset_days": smap_rec.get("date_offset_days", 0),
            "rainfall_source_file": rain_rec.get("rainfall_source_file", ""),
            "smap_source_file": smap_rec.get("source_file", ""),
            "rainfall_units": "mm/day",
            "soil_moisture_units": "cm^3/cm^3",
        }

    def align_batch(
        self,
        locations: List[Dict[str, Union[float, str]]],
        obs_date: date,
        smap_tolerance_days: int = 0,
    ) -> pd.DataFrame:
        """Align IMERG and SMAP features for a batch of locations on a specific date using optimized batch extraction.

        Args:
            locations: List of dicts with 'latitude' and 'longitude'.
            obs_date: Observation date.
            smap_tolerance_days: Allowed SMAP date matching tolerance.

        Returns:
            pandas DataFrame containing aligned environmental feature records.
        """
        # Batch extract SMAP soil moisture in a single file-open pass
        smap_df = self.smap_proc.extract_batch(locations, obs_date, tolerance_days=smap_tolerance_days)

        records = []
        for loc in locations:
            lat = float(loc["latitude"])
            lon = float(loc["longitude"])

            # Extract IMERG rolling rainfall features
            rain_rec = self.imerg_proc.extract_point_rolling(lat, lon, obs_date)
            r1d = rain_rec["rainfall_1d"]
            r3d = rain_rec["rainfall_3d"]
            r7d = rain_rec["rainfall_7d"]
            r_status = rain_rec["rainfall_data_status"]

            # Match SMAP record from batch
            smap_row = smap_df[(smap_df["latitude"] == lat) & (smap_df["longitude"] == lon)]
            if not smap_row.empty:
                s_rec = smap_row.iloc[0].to_dict()
                sm = s_rec.get("soil_moisture", np.nan)
                sm_status = s_rec.get("smap_data_status", "MISSING_FILE")
                sm_qual = s_rec.get("soil_moisture_quality", "INVALID")
                sm_time = s_rec.get("soil_moisture_observation_time", "N/A")
                sm_src = s_rec.get("soil_moisture_source", "INVALID_RETRIEVAL")
                sm_file = s_rec.get("source_file", "")
                sm_match_date = s_rec.get("matched_date")
                sm_offset = s_rec.get("date_offset_days", 0)
            else:
                sm = np.nan
                sm_status = "MISSING_FILE"
                sm_qual = "INVALID"
                sm_time = "N/A"
                sm_src = "NO_FILE"
                sm_file = ""
                sm_match_date = None
                sm_offset = 0

            r_valid = not np.isnan(r1d)
            sm_valid = not np.isnan(sm)

            if r_valid and sm_valid:
                overall_status = "COMPLETE"
            elif r_valid:
                overall_status = "PARTIAL_RAINFALL_ONLY"
            elif sm_valid:
                overall_status = "PARTIAL_SOIL_MOISTURE_ONLY"
            else:
                overall_status = "INSUFFICIENT_DATA"

            row = dict(loc)
            row.update({
                "latitude": lat,
                "longitude": lon,
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "rainfall_1d": r1d,
                "rainfall_3d": r3d,
                "rainfall_7d": r7d,
                "soil_moisture": sm,
                "soil_moisture_quality": sm_qual,
                "soil_moisture_observation_time": sm_time,
                "soil_moisture_source": sm_src,
                "rainfall_data_status": r_status,
                "soil_moisture_data_status": sm_status,
                "overall_alignment_status": overall_status,
                "smap_matched_date": sm_match_date,
                "smap_date_offset_days": sm_offset,
                "rainfall_source_file": rain_rec.get("rainfall_source_file", ""),
                "smap_source_file": sm_file,
                "rainfall_units": "mm/day",
                "soil_moisture_units": "cm^3/cm^3",
            })
            records.append(row)

        return pd.DataFrame(records)
