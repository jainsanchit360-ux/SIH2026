import json
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd
from fastapi import HTTPException

from backend.app.core.config import settings
from backend.app.schemas.alert_schema import (
    AlertResponse,
    ResponseNoteItem,
    StatusAuditItem,
    AlertSummaryResponse,
    PROTOTYPE_WARNING_DISCLAIMER,
)

logger = logging.getLogger(__name__)

# Valid operational workflow state transitions mapping
ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "NEW": ["ACKNOWLEDGED"],
    "ACKNOWLEDGED": ["MONITORING", "RESPONSE_DISPATCHED"],
    "MONITORING": ["RESPONSE_DISPATCHED", "RESOLVED"],
    "RESPONSE_DISPATCHED": ["RESOLVED"],
    "RESOLVED": [],
}


def _get_utc_now_str() -> str:
    """Helper to return current ISO timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class AlertService:
    """Singleton service for persistent SQLite alert management and operational workflows."""

    def __init__(self, db_path: Optional[Path] = None):
        self.settings = settings
        self.db_path = db_path or (self.settings.DATA_PROCESSED_DIR.parent / "alerts.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Helper to get a SQLite connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize SQLite database tables and indexes if not existing."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    site_id TEXT NOT NULL,
                    site_name TEXT NOT NULL,
                    state TEXT NOT NULL,
                    district TEXT,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    observation_date TEXT NOT NULL,
                    risk_score REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    static_susceptibility_score REAL,
                    dynamic_trigger_score REAL,
                    rainfall_1d REAL,
                    rainfall_3d REAL,
                    rainfall_7d REAL,
                    soil_moisture REAL,
                    reason TEXT NOT NULL,
                    major_risk_factors TEXT,
                    risk_explanation TEXT,
                    what_changed TEXT,
                    data_source TEXT NOT NULL,
                    simulation_mode INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    acknowledged_at TEXT,
                    acknowledged_by TEXT,
                    response_notes TEXT,
                    audit_history TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_site ON alerts(site_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_source ON alerts(data_source)")
            conn.commit()

    def sync_historical_alerts(self, risk_df: Optional[pd.DataFrame] = None) -> int:
        """Deterministically generate prototype alerts for historical records with risk >= 40.0.

        Deduplicates alerts by (site_id, observation_date, risk_level, data_source).
        """
        if risk_df is None or risk_df.empty:
            risk_file = self.settings.DATA_PROCESSED_DIR / "current_landslide_risk.parquet"
            if risk_file.exists():
                risk_df = pd.read_parquet(risk_file)
            else:
                return 0

        # Filter for valid risk observations with MODERATE or HIGH risk (score >= 40.0)
        valid_alerts_df = risk_df[
            (risk_df["current_risk_score"].notna()) &
            (risk_df["current_risk_score"] >= 40.0)
        ].copy()

        if valid_alerts_df.empty:
            return 0

        created_count = 0
        now_str = _get_utc_now_str()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for _, row in valid_alerts_df.iterrows():
                site_id = str(row.get("site_id", "SITE"))
                obs_date = str(row.get("observation_date", ""))
                risk_score = float(row.get("current_risk_score", 0.0))
                risk_level = str(row.get("current_risk_level", "MODERATE")).upper()
                severity = "HIGH" if risk_score >= 70.0 else "MODERATE"
                data_source = "OFFLINE_HISTORICAL_CACHE"

                alert_id = f"ALT-{obs_date.replace('-', '')}-{site_id}-{severity}"

                # Check deduplication
                cursor.execute("SELECT alert_id FROM alerts WHERE alert_id = ?", (alert_id,))
                if cursor.fetchone():
                    continue

                major_factors = row.get("major_risk_factors")
                if isinstance(major_factors, (list, np.ndarray)):
                    major_factors_json = json.dumps([str(x) for x in major_factors])
                elif isinstance(major_factors, str):
                    major_factors_json = json.dumps([major_factors])
                else:
                    major_factors_json = json.dumps(["Elevated environmental trigger index"])

                reason = f"Historical {severity} landslide risk index ({risk_score:.1f}/100) recorded on {obs_date}."

                init_audit = [
                    StatusAuditItem(
                        timestamp=now_str,
                        from_status="NONE",
                        to_status="NEW",
                        performed_by="System Alert Synchronizer"
                    ).model_dump()
                ]

                cursor.execute("""
                    INSERT INTO alerts (
                        alert_id, site_id, site_name, state, district, latitude, longitude,
                        created_at, updated_at, observation_date, risk_score, risk_level, severity,
                        static_susceptibility_score, dynamic_trigger_score, rainfall_1d, rainfall_3d, rainfall_7d, soil_moisture,
                        reason, major_risk_factors, risk_explanation, what_changed,
                        data_source, simulation_mode, status, acknowledged_at, acknowledged_by,
                        response_notes, audit_history
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?
                    )
                """, (
                    alert_id,
                    site_id,
                    str(row.get("site_name", "Monitored Site")),
                    str(row.get("state", "NER")),
                    str(row.get("district", "NER")),
                    float(row.get("latitude")),
                    float(row.get("longitude")),
                    now_str,
                    now_str,
                    obs_date,
                    risk_score,
                    risk_level,
                    severity,
                    float(row["static_susceptibility_score"]) if pd.notna(row.get("static_susceptibility_score")) else None,
                    float(row["dynamic_trigger_score"]) if pd.notna(row.get("dynamic_trigger_score")) else None,
                    float(row["rainfall_1d"]) if pd.notna(row.get("rainfall_1d")) else None,
                    float(row["rainfall_3d"]) if pd.notna(row.get("rainfall_3d")) else None,
                    float(row["rainfall_7d"]) if pd.notna(row.get("rainfall_7d")) else None,
                    float(row["soil_moisture"]) if pd.notna(row.get("soil_moisture")) else None,
                    reason,
                    major_factors_json,
                    str(row.get("risk_explanation", "")),
                    str(row.get("what_changed", "")),
                    data_source,
                    0,  # simulation_mode = false
                    "NEW",
                    None,
                    None,
                    json.dumps([]),
                    json.dumps(init_audit)
                ))
                created_count += 1
            conn.commit()

        return created_count

    def _row_to_alert_response(self, row: sqlite3.Row) -> AlertResponse:
        """Convert SQLite database row into validated AlertResponse pydantic object."""
        notes_raw = row["response_notes"]
        notes_list = json.loads(notes_raw) if notes_raw else []

        audit_raw = row["audit_history"]
        audit_list = json.loads(audit_raw) if audit_raw else []

        factors_raw = row["major_risk_factors"]
        factors_list = json.loads(factors_raw) if factors_raw else []

        return AlertResponse(
            alert_id=row["alert_id"],
            site_id=row["site_id"],
            site_name=row["site_name"],
            state=row["state"],
            district=row["district"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            observation_date=row["observation_date"],
            risk_score=row["risk_score"],
            risk_level=row["risk_level"],
            severity=row["severity"],
            static_susceptibility_score=row["static_susceptibility_score"],
            dynamic_trigger_score=row["dynamic_trigger_score"],
            rainfall_1d=row["rainfall_1d"],
            rainfall_3d=row["rainfall_3d"],
            rainfall_7d=row["rainfall_7d"],
            soil_moisture=row["soil_moisture"],
            reason=row["reason"],
            major_risk_factors=factors_list,
            risk_explanation=row["risk_explanation"],
            what_changed=row["what_changed"],
            data_source=row["data_source"],
            simulation_mode=bool(row["simulation_mode"]),
            status=row["status"],
            acknowledged_at=row["acknowledged_at"],
            acknowledged_by=row["acknowledged_by"],
            response_notes=[ResponseNoteItem(**n) for n in notes_list],
            audit_history=[StatusAuditItem(**a) for a in audit_list],
            calibration_disclaimer=PROTOTYPE_WARNING_DISCLAIMER,
        )

    def get_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        site_id: Optional[str] = None,
        simulation_mode: Optional[bool] = None,
    ) -> List[AlertResponse]:
        """Retrieve filtered alert list sorted by creation timestamp descending."""
        query = "SELECT * FROM alerts WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status.upper())
        if severity:
            query += " AND severity = ?"
            params.append(severity.upper())
        if site_id:
            query += " AND site_id = ?"
            params.append(site_id)
        if simulation_mode is not None:
            query += " AND simulation_mode = ?"
            params.append(1 if simulation_mode else 0)

        query += " ORDER BY observation_date DESC, created_at DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_alert_response(r) for r in rows]

    def get_active_alerts(self) -> List[AlertResponse]:
        """Retrieve all active un-resolved alerts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM alerts WHERE status IN ('NEW', 'ACKNOWLEDGED', 'MONITORING', 'RESPONSE_DISPATCHED') ORDER BY risk_score DESC, observation_date DESC"
            )
            rows = cursor.fetchall()
            return [self._row_to_alert_response(r) for r in rows]

    def get_alert_history(self) -> List[AlertResponse]:
        """Retrieve complete alert history log."""
        return self.get_alerts()

    def get_alert_by_id(self, alert_id: str) -> AlertResponse:
        """Retrieve single alert record by alert_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
            return self._row_to_alert_response(row)

    def update_alert_status(self, alert_id: str, new_status: str, performed_by: str = "Operator", note: Optional[str] = None) -> AlertResponse:
        """Update alert workflow status with strict transition state machine rules."""
        new_status_upper = new_status.upper().strip()
        now_str = _get_utc_now_str()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")

            current_status = row["status"]

            # Validate allowed workflow state transition
            if current_status != new_status_upper:
                allowed_targets = ALLOWED_TRANSITIONS.get(current_status, [])
                if new_status_upper not in allowed_targets:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Invalid workflow state transition from '{current_status}' to '{new_status_upper}'. Allowed targets: {allowed_targets}"
                    )

            # Audit history update
            audit_list = json.loads(row["audit_history"]) if row["audit_history"] else []
            audit_list.append(
                StatusAuditItem(
                    timestamp=now_str,
                    from_status=current_status,
                    to_status=new_status_upper,
                    performed_by=performed_by,
                ).model_dump()
            )

            # Response notes update if note provided
            notes_list = json.loads(row["response_notes"]) if row["response_notes"] else []
            if note:
                notes_list.append(
                    ResponseNoteItem(
                        timestamp=now_str,
                        note=note,
                        author=performed_by,
                    ).model_dump()
                )

            acknowledged_at = row["acknowledged_at"]
            acknowledged_by = row["acknowledged_by"]

            if new_status_upper == "ACKNOWLEDGED" and not acknowledged_at:
                acknowledged_at = now_str
                acknowledged_by = performed_by

            cursor.execute("""
                UPDATE alerts
                SET status = ?, updated_at = ?, acknowledged_at = ?, acknowledged_by = ?, response_notes = ?, audit_history = ?
                WHERE alert_id = ?
            """, (
                new_status_upper,
                now_str,
                acknowledged_at,
                acknowledged_by,
                json.dumps(notes_list),
                json.dumps(audit_list),
                alert_id,
            ))
            conn.commit()

            cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
            updated_row = cursor.fetchone()
            return self._row_to_alert_response(updated_row)

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "District Control Room") -> AlertResponse:
        """Convenience method to transition alert from NEW to ACKNOWLEDGED."""
        return self.update_alert_status(alert_id, "ACKNOWLEDGED", performed_by=acknowledged_by)

    def add_response_note(self, alert_id: str, note_text: str, author: str = "Authority Officer") -> AlertResponse:
        """Add an operational response note to an alert."""
        now_str = _get_utc_now_str()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")

            notes_list = json.loads(row["response_notes"]) if row["response_notes"] else []
            notes_list.append(
                ResponseNoteItem(
                    timestamp=now_str,
                    note=note_text,
                    author=author,
                ).model_dump()
            )

            cursor.execute("""
                UPDATE alerts
                SET response_notes = ?, updated_at = ?
                WHERE alert_id = ?
            """, (json.dumps(notes_list), now_str, alert_id))
            conn.commit()

            cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
            return self._row_to_alert_response(cursor.fetchone())

    def create_simulated_alert(self, sim_data: Dict[str, Any]) -> AlertResponse:
        """Create a SIMULATED_DEMO operational alert from demo scenario simulation result."""
        now_str = _get_utc_now_str()
        site_id = sim_data.get("site_id", "DEMO_SITE")
        sim_score = float(sim_data.get("simulated_current_risk_score", sim_data.get("current_risk_score", 75.0)))
        sim_level = str(sim_data.get("simulated_current_risk_level", sim_data.get("current_risk_level", "HIGH"))).upper()
        severity = "HIGH" if sim_score >= 70.0 else "MODERATE"

        # Unique alert ID for simulation run
        sim_ts = datetime.now().strftime("%H%M%S")
        alert_id = f"ALT-SIM-{sim_ts}-{site_id}"

        obs_date = str(sim_data.get("observation_date", datetime.now().strftime("%Y-%m-%d")))
        scenario_name = sim_data.get('scenario_name', 'What-If Monsoon Scenario')
        reason = f"Simulated {scenario_name}: Trigger score reached {sim_data.get('dynamic_trigger_score', 80):.1f}/100."

        init_audit = [
            StatusAuditItem(
                timestamp=now_str,
                from_status="NONE",
                to_status="NEW",
                performed_by="Demo Simulation Engine"
            ).model_dump()
        ]

        factors = sim_data.get("major_risk_factors", ["Simulated rainfall downpour", "Saturated soil moisture"])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alerts (
                    alert_id, site_id, site_name, state, district, latitude, longitude,
                    created_at, updated_at, observation_date, risk_score, risk_level, severity,
                    static_susceptibility_score, dynamic_trigger_score, rainfall_1d, rainfall_3d, rainfall_7d, soil_moisture,
                    reason, major_risk_factors, risk_explanation, what_changed,
                    data_source, simulation_mode, status, acknowledged_at, acknowledged_by,
                    response_notes, audit_history
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?
                )
            """, (
                alert_id,
                site_id,
                str(sim_data.get("site_name", "Demo Location")),
                str(sim_data.get("state", "NER")),
                str(sim_data.get("district", "NER")),
                float(sim_data.get("latitude", 25.5)),
                float(sim_data.get("longitude", 92.5)),
                now_str,
                now_str,
                obs_date,
                sim_score,
                sim_level,
                severity,
                float(sim_data["static_susceptibility_score"]) if sim_data.get("static_susceptibility_score") is not None else 65.0,
                float(sim_data["dynamic_trigger_score"]) if sim_data.get("dynamic_trigger_score") is not None else 80.0,
                float(sim_data["simulated_rainfall_1d"]) if sim_data.get("simulated_rainfall_1d") is not None else 85.0,
                float(sim_data["simulated_rainfall_3d"]) if sim_data.get("simulated_rainfall_3d") is not None else 160.0,
                float(sim_data["simulated_rainfall_7d"]) if sim_data.get("simulated_rainfall_7d") is not None else 260.0,
                float(sim_data["simulated_soil_moisture"]) if sim_data.get("simulated_soil_moisture") is not None else 0.42,
                reason,
                json.dumps(factors),
                f"Simulated operational warning under scenario: {scenario_name}.",
                f"Simulated rainfall spike caused risk to increase from baseline.",
                "SIMULATED_DEMO",
                1,  # simulation_mode = true
                "NEW",
                None,
                None,
                json.dumps([]),
                json.dumps(init_audit)
            ))
            conn.commit()

            cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
            return self._row_to_alert_response(cursor.fetchone())

    def reset_demo_alerts(self) -> int:
        """Purge simulated demo operational alert records from SQLite DB.

        Real historical processed Parquet datasets remain 100% untouched.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM alerts WHERE simulation_mode = 1 OR data_source = 'SIMULATED_DEMO'")
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

    def get_alert_summary(self) -> AlertSummaryResponse:
        """Compute aggregated alert metrics for Authority Command Center summary cards."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM alerts WHERE status IN ('NEW', 'ACKNOWLEDGED', 'MONITORING', 'RESPONSE_DISPATCHED')")
            active_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'NEW'")
            unack_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts WHERE severity = 'HIGH' AND status != 'RESOLVED'")
            high_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts WHERE severity = 'MODERATE' AND status != 'RESOLVED'")
            mod_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'RESPONSE_DISPATCHED'")
            dispatch_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'RESOLVED'")
            resolved_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts WHERE risk_level = 'INSUFFICIENT_DATA'")
            insufficient_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts WHERE simulation_mode = 1")
            sim_count = cursor.fetchone()[0]

            return AlertSummaryResponse(
                active_warnings_count=active_count,
                unacknowledged_alerts_count=unack_count,
                high_risk_sites_count=high_count,
                moderate_risk_sites_count=mod_count,
                response_dispatched_count=dispatch_count,
                resolved_count=resolved_count,
                insufficient_data_sites_count=insufficient_count,
                simulated_alerts_count=sim_count,
                last_updated_at=_get_utc_now_str(),
            )
