"""Unit and integration tests for Phase 10 Early Warning Alert System & SQLite Storage."""

import pytest
import sqlite3
import pandas as pd
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.alert_service import AlertService, ALLOWED_TRANSITIONS
from backend.app.schemas.alert_schema import AlertResponse, AlertSummaryResponse
from fastapi import HTTPException


@pytest.fixture
def temp_db_path(tmp_path):
    """Fixture providing temporary SQLite DB path."""
    return tmp_path / "test_alerts.db"


@pytest.fixture
def alert_service(temp_db_path):
    """Fixture providing isolated AlertService instance."""
    return AlertService(db_path=temp_db_path)


@pytest.fixture
def sample_risk_df():
    """Fixture providing synthetic risk dataframe with MODERATE and HIGH risk rows."""
    records = [
        {
            "site_id": "GSI_SITE_01",
            "site_name": "Kukinala slide",
            "state": "Assam",
            "district": "Hailakandi",
            "latitude": 24.27,
            "longitude": 92.50,
            "observation_date": "2025-07-04",
            "current_risk_score": 82.5,
            "current_risk_level": "HIGH",
            "static_susceptibility_score": 75.0,
            "dynamic_trigger_score": 88.0,
            "rainfall_1d": 85.0,
            "rainfall_3d": 160.0,
            "rainfall_7d": 260.0,
            "soil_moisture": 0.42,
            "major_risk_factors": ["High antecedent rainfall", "Steep slope"],
            "risk_explanation": "Severe risk under monsoon downpour",
            "what_changed": "Rainfall increased score by 15 points",
        },
        {
            "site_id": "GSI_SITE_02",
            "site_name": "Shillong slide",
            "state": "Meghalaya",
            "district": "East Khasi Hills",
            "latitude": 25.578,
            "longitude": 91.893,
            "observation_date": "2025-07-04",
            "current_risk_score": 52.0,
            "current_risk_level": "MODERATE",
            "static_susceptibility_score": 60.0,
            "dynamic_trigger_score": 45.0,
            "rainfall_1d": 25.0,
            "rainfall_3d": 50.0,
            "rainfall_7d": 90.0,
            "soil_moisture": 0.28,
            "major_risk_factors": ["Moderate rainfall accumulation"],
            "risk_explanation": "Advisory risk level",
            "what_changed": "Stable conditions",
        },
        {
            "site_id": "GSI_SITE_03",
            "site_name": "Low risk site",
            "state": "Assam",
            "district": "Cachar",
            "latitude": 24.795,
            "longitude": 93.045,
            "observation_date": "2025-07-04",
            "current_risk_score": 22.0,
            "current_risk_level": "LOW",
            "static_susceptibility_score": 30.0,
            "dynamic_trigger_score": 15.0,
            "rainfall_1d": 2.0,
            "rainfall_3d": 5.0,
            "rainfall_7d": 10.0,
            "soil_moisture": 0.15,
            "major_risk_factors": [],
            "risk_explanation": "Low risk",
            "what_changed": "None",
        },
    ]
    return pd.DataFrame(records)


def test_sqlite_db_initialization(temp_db_path, alert_service):
    """Test that SQLite database and table schemas initialize correctly."""
    assert temp_db_path.exists()
    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "alerts"
    conn.close()


def test_sync_historical_alerts_deduplication(alert_service, sample_risk_df):
    """Test deterministic creation of historical alerts and deduplication logic."""
    count1 = alert_service.sync_historical_alerts(sample_risk_df)
    # Sites 01 and 02 have risk >= 40.0 -> 2 alerts created
    assert count1 == 2

    # Running sync a second time should create 0 duplicate alerts
    count2 = alert_service.sync_historical_alerts(sample_risk_df)
    assert count2 == 0

    alerts = alert_service.get_alerts()
    assert len(alerts) == 2
    for alt in alerts:
        assert alt.data_source == "OFFLINE_HISTORICAL_CACHE"
        assert alt.simulation_mode is False
        assert alt.status == "NEW"


def test_valid_workflow_state_transitions(alert_service, sample_risk_df):
    """Test valid sequential state transitions: NEW -> ACKNOWLEDGED -> MONITORING -> RESPONSE_DISPATCHED -> RESOLVED."""
    alert_service.sync_historical_alerts(sample_risk_df)
    alerts = alert_service.get_alerts()
    alert_id = alerts[0].alert_id

    # 1. NEW -> ACKNOWLEDGED
    a1 = alert_service.acknowledge_alert(alert_id, acknowledged_by="Officer Jain")
    assert a1.status == "ACKNOWLEDGED"
    assert a1.acknowledged_by == "Officer Jain"
    assert a1.acknowledged_at is not None

    # 2. ACKNOWLEDGED -> MONITORING
    a2 = alert_service.update_alert_status(alert_id, "MONITORING", performed_by="Field Unit")
    assert a2.status == "MONITORING"

    # 3. MONITORING -> RESPONSE_DISPATCHED
    a3 = alert_service.update_alert_status(alert_id, "RESPONSE_DISPATCHED", performed_by="SDRF Control Room")
    assert a3.status == "RESPONSE_DISPATCHED"

    # 4. RESPONSE_DISPATCHED -> RESOLVED
    a4 = alert_service.update_alert_status(alert_id, "RESOLVED", performed_by="District Magistrate")
    assert a4.status == "RESOLVED"
    assert len(a4.audit_history) >= 4


def test_invalid_workflow_state_transition_blocked(alert_service, sample_risk_df):
    """Test that invalid state jumps (e.g. NEW directly to RESOLVED) raise HTTP 422 error."""
    alert_service.sync_historical_alerts(sample_risk_df)
    alerts = alert_service.get_alerts()
    alert_id = alerts[0].alert_id

    # Transition directly from NEW to RESOLVED is invalid
    with pytest.raises(HTTPException) as exc_info:
        alert_service.update_alert_status(alert_id, "RESOLVED")
    assert exc_info.value.status_code == 422
    assert "Invalid workflow state transition" in exc_info.value.detail


def test_add_operational_response_notes(alert_service, sample_risk_df):
    """Test adding operational response notes to an alert."""
    alert_service.sync_historical_alerts(sample_risk_df)
    alerts = alert_service.get_alerts()
    alert_id = alerts[0].alert_id

    updated = alert_service.add_response_note(
        alert_id,
        note_text="SDRF team dispatched to Kukinala road sector.",
        author="Control Room Operator"
    )

    assert len(updated.response_notes) == 1
    assert updated.response_notes[0].note == "SDRF team dispatched to Kukinala road sector."
    assert updated.response_notes[0].author == "Control Room Operator"


def test_create_simulated_alert_and_reset(alert_service, sample_risk_df):
    """Test creating a SIMULATED_DEMO alert and verifying scoped demo reset."""
    alert_service.sync_historical_alerts(sample_risk_df)
    historical_count = len(alert_service.get_alerts())
    assert historical_count == 2

    # Create simulated demo alert
    sim_data = {
        "site_id": "GSI_SITE_01",
        "site_name": "Kukinala slide",
        "state": "Assam",
        "district": "Hailakandi",
        "latitude": 24.27,
        "longitude": 92.50,
        "observation_date": "2025-09-30",
        "simulated_current_risk_score": 88.0,
        "simulated_current_risk_level": "HIGH",
        "static_susceptibility_score": 75.0,
        "dynamic_trigger_score": 92.0,
        "simulated_rainfall_1d": 120.0,
        "simulated_rainfall_3d": 210.0,
        "simulated_rainfall_7d": 350.0,
        "simulated_soil_moisture": 0.48,
        "scenario_name": "Cloudburst Demo Simulation",
    }

    sim_alert = alert_service.create_simulated_alert(sim_data)
    assert sim_alert.data_source == "SIMULATED_DEMO"
    assert sim_alert.simulation_mode is True
    assert sim_alert.severity == "HIGH"
    assert sim_alert.status == "NEW"

    # Total alerts should now be 3 (2 historical + 1 demo)
    assert len(alert_service.get_alerts()) == 3

    # Run demo reset
    deleted = alert_service.reset_demo_alerts()
    assert deleted == 1

    # Remaining alerts should strictly equal the 2 historical alerts
    remaining = alert_service.get_alerts()
    assert len(remaining) == 2
    for a in remaining:
        assert a.data_source == "OFFLINE_HISTORICAL_CACHE"
        assert a.simulation_mode is False


def test_alert_summary_counters(alert_service, sample_risk_df):
    """Test aggregated summary counters computation."""
    alert_service.sync_historical_alerts(sample_risk_df)
    summary = alert_service.get_alert_summary()

    assert summary.active_warnings_count == 2
    assert summary.unacknowledged_alerts_count == 2
    assert summary.high_risk_sites_count == 1
    assert summary.moderate_risk_sites_count == 1
    assert summary.simulated_alerts_count == 0


def test_alert_api_endpoints_integration():
    """Integration test verifying FastAPI Phase 10 REST endpoints live behavior."""
    client = TestClient(app)

    # 1. GET /api/v1/alerts/summary
    res_sum = client.get("/api/v1/alerts/summary")
    assert res_sum.status_code == 200
    sum_json = res_sum.json()
    assert "active_warnings_count" in sum_json

    # 2. GET /api/v1/alerts
    res_list = client.get("/api/v1/alerts")
    assert res_list.status_code == 200
    alerts = res_list.json()
    assert len(alerts) >= 0

    if alerts:
        target_id = alerts[0]["alert_id"]

        # 3. POST /api/v1/alerts/{alert_id}/acknowledge
        res_ack = client.post(
            f"/api/v1/alerts/{target_id}/acknowledge",
            json={"acknowledged_by": "Test Suite Inspector"}
        )
        assert res_ack.status_code == 200
        assert res_ack.json()["status"] == "ACKNOWLEDGED"

        # 4. POST /api/v1/alerts/{alert_id}/notes
        res_note = client.post(
            f"/api/v1/alerts/{target_id}/notes",
            json={"note": "Automated verification note.", "author": "Pytest Inspector"}
        )
        assert res_note.status_code == 200

    # 5. POST /api/v1/demo/simulate-and-alert
    sim_payload = {
        "site_id": "GSI_SITE_01",
        "simulated_rainfall_1d": 110.0,
        "simulated_rainfall_3d": 190.0,
        "simulated_rainfall_7d": 310.0,
        "simulated_soil_moisture": 0.45,
        "scenario_name": "Heavy Monsoon Downpour Test",
    }
    res_sim = client.post("/api/v1/demo/simulate-and-alert", json=sim_payload)
    assert res_sim.status_code == 200
    sim_alert = res_sim.json()
    assert sim_alert["data_source"] == "SIMULATED_DEMO"
    assert sim_alert["simulation_mode"] is True

    # 6. POST /api/v1/demo/reset
    res_reset = client.post("/api/v1/demo/reset")
    assert res_reset.status_code == 200
    assert res_reset.json()["scientific_datasets_mutated"] is False
