"""Comprehensive unit tests for Phase 8 FastAPI Backend Endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test GET / returns 200 OK and valid project metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "ResQtech"
    assert data["offline_mode"] is True
    assert data["is_live"] is False
    assert "swagger_docs" in data


def test_health_endpoints():
    """Test GET /health and GET /api/v1/health return 200 OK status."""
    res1 = client.get("/health")
    assert res1.status_code == 200
    assert res1.json()["status"] == "ok"

    res2 = client.get("/api/v1/health")
    assert res2.status_code == 200
    assert res2.json()["status"] == "ok"


def test_system_status_endpoint():
    """Test GET /api/v1/system/status returns system metrics, versions, and disclaimer."""
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert data["app_name"] == "ResQtech"
    assert data["api_version"] == "0.1.0-prototype"
    assert data["offline_mode"] is True
    assert data["is_live"] is False
    assert data["processed_data_status"] == "AVAILABLE"
    assert "last_available_observation_date" in data
    assert len(data["model_features"]) == 4
    assert "PROTOTYPE OPERATIONAL PARAMETERS" in data["calibration_disclaimer"]


def test_locations_endpoint():
    """Test GET /api/v1/locations returns monitored pilot locations list."""
    response = client.get("/api/v1/locations")
    assert response.status_code == 200
    locations = response.json()
    assert isinstance(locations, list)
    if len(locations) > 0:
        loc = locations[0]
        assert "site_id" in loc
        assert "site_name" in loc
        assert "latitude" in loc
        assert "longitude" in loc


def test_latest_risk_endpoint():
    """Test GET /api/v1/risk/latest returns latest risk assessments for all sites."""
    response = client.get("/api/v1/risk/latest")
    assert response.status_code == 200
    records = response.json()
    assert isinstance(records, list)
    if len(records) > 0:
        rec = records[0]
        assert 0.0 <= rec["current_risk_score"] <= 100.0
        assert rec["current_risk_level"] in ["LOW", "MODERATE", "HIGH", "INSUFFICIENT_DATA"]
        assert rec["freshness_status"] == "OFFLINE_HISTORICAL_CACHE"
        assert rec["is_live"] is False
        assert "calibration_disclaimer" in rec


def test_site_risk_detail_and_not_found():
    """Test GET /api/v1/risk/{site_id} for valid site and 404 for invalid site."""
    locations_res = client.get("/api/v1/locations")
    locations = locations_res.json()
    if locations:
        valid_site_id = locations[0]["site_id"]
        res = client.get(f"/api/v1/risk/{valid_site_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["site_id"] == valid_site_id
        assert 0.0 <= data["current_risk_score"] <= 100.0

    invalid_res = client.get("/api/v1/risk/NON_EXISTENT_SITE_999")
    assert invalid_res.status_code == 404
    assert "not found" in invalid_res.json()["detail"].lower()


def test_site_timeseries_and_date_filtering():
    """Test GET /api/v1/risk/{site_id}/timeseries returns sorted list and supports start/end date filters."""
    locations_res = client.get("/api/v1/locations")
    locations = locations_res.json()
    if locations:
        site_id = locations[0]["site_id"]
        res = client.get(f"/api/v1/risk/{site_id}/timeseries")
        assert res.status_code == 200
        ts = res.json()
        assert isinstance(ts, list)
        if len(ts) > 1:
            assert ts[0]["observation_date"] <= ts[-1]["observation_date"]

        # Date filtering test
        res_filtered = client.get(f"/api/v1/risk/{site_id}/timeseries?start_date=2025-05-01&end_date=2025-06-01")
        assert res_filtered.status_code == 200
        filtered_ts = res_filtered.json()
        for item in filtered_ts:
            assert "2025-05-01" <= item["observation_date"] <= "2025-06-01"


def test_environment_susceptibility_explanation_endpoints():
    """Test GET environment, susceptibility, and explanation endpoints."""
    locations_res = client.get("/api/v1/locations")
    locations = locations_res.json()
    if locations:
        site_id = locations[0]["site_id"]

        env_res = client.get(f"/api/v1/environment/{site_id}")
        assert env_res.status_code == 200
        env_data = env_res.json()
        assert "dynamic_trigger_score" in env_data
        assert env_data["data_status"] in ["VALID", "PARTIAL_RAINFALL_ONLY", "INSUFFICIENT_DATA"]

        sus_res = client.get(f"/api/v1/susceptibility/{site_id}")
        assert sus_res.status_code == 200
        sus_data = sus_res.json()
        assert "static_susceptibility_score" in sus_data
        assert "probability" not in sus_data  # Scientific terminology check

        exp_res = client.get(f"/api/v1/explanation/{site_id}")
        assert exp_res.status_code == 200
        assert "risk_explanation" in exp_res.json()


def test_map_risk_geojson_spec():
    """Test GET /api/v1/map/risk returns valid GeoJSON FeatureCollection with [longitude, latitude] coordinates."""
    response = client.get("/api/v1/map/risk")
    assert response.status_code == 200
    geojson = response.json()
    
    assert geojson["type"] == "FeatureCollection"
    assert "features" in geojson
    assert isinstance(geojson["features"], list)

    if len(geojson["features"]) > 0:
        feature = geojson["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        
        coords = feature["geometry"]["coordinates"]
        assert len(coords) == 2
        
        # GeoJSON Order Rule: [longitude, latitude]
        lon, lat = coords[0], coords[1]
        assert 87.0 <= lon <= 98.0  # NER Longitude range
        assert 21.0 <= lat <= 30.0  # NER Latitude range
        
        props = feature["properties"]
        assert "current_risk_score" in props
        assert "current_risk_level" in props


def test_demo_simulate_valid_and_comparison():
    """Test POST /api/v1/demo/simulate returns simulated risk response with baseline comparison."""
    payload = {
        "simulated_rainfall_1d": 140.0,
        "simulated_rainfall_3d": 250.0,
        "simulated_rainfall_7d": 400.0,
        "simulated_soil_moisture": 0.45,
        "scenario_name": "Extreme Monsoon Downpour",
    }
    response = client.post("/api/v1/demo/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["simulation_mode"] is True
    assert data["data_source"] == "SIMULATED_DEMO"
    assert data["scenario_name"] == "Extreme Monsoon Downpour"
    assert 0.0 <= data["current_risk_score"] <= 100.0
    assert data["current_risk_level"] in ["LOW", "MODERATE", "HIGH"]
    assert "simulated_current_risk_score" in data
    assert "simulated_current_risk_level" in data
    assert "[DEMO SIMULATION:" in data["risk_explanation"]


def test_demo_simulate_invalid_inputs():
    """Test POST /api/v1/demo/simulate returns 422 for invalid negative rainfall or out-of-range soil moisture."""
    # Negative rainfall
    res1 = client.post("/api/v1/demo/simulate", json={
        "simulated_rainfall_1d": -10.0,
        "simulated_rainfall_3d": 100.0,
        "simulated_rainfall_7d": 200.0,
        "simulated_soil_moisture": 0.35
    })
    assert res1.status_code == 422

    # Soil moisture > 100%
    res2 = client.post("/api/v1/demo/simulate", json={
        "simulated_rainfall_1d": 50.0,
        "simulated_rainfall_3d": 100.0,
        "simulated_rainfall_7d": 200.0,
        "simulated_soil_moisture": 150.0
    })
    assert res2.status_code == 422
