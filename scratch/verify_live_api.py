import urllib.request
import urllib.parse
import json

BASE_URL = "http://127.0.0.1:8000"

def get_json(url_path):
    url = f"{BASE_URL}{url_path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200, f"Expected 200 for {url}, got {resp.status}"
        return json.loads(resp.read().decode())

def post_json(url_path, data):
    url = f"{BASE_URL}{url_path}"
    json_bytes = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=json_bytes, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200, f"Expected 200 for {url}, got {resp.status}"
        return json.loads(resp.read().decode())

def run_live_tests():
    print("=== LIVE HTTP SMOKE TEST ===")
    
    # 1. Health
    h1 = get_json("/health")
    print("1. GET /health ->", h1["status"])
    assert h1["status"] == "ok"
    
    # 2. System Status
    sys_status = get_json("/api/v1/system/status")
    print("2. GET /api/v1/system/status -> API Version:", sys_status["api_version"], "| Status:", sys_status["status"])
    assert sys_status["api_version"] == "0.1.0-prototype"
    assert sys_status["offline_mode"] is True
    
    # 3. Locations
    locations = get_json("/api/v1/locations")
    print(f"3. GET /api/v1/locations -> Found {len(locations)} locations.")
    assert len(locations) > 0
    sample_site_id = locations[0]["site_id"]
    print(f"   Selected sample site_id: {sample_site_id} ({locations[0]['site_name']})")
    
    # 4. Latest Risk
    latest_risk = get_json("/api/v1/risk/latest")
    print(f"4. GET /api/v1/risk/latest -> Returned {len(latest_risk)} site risk records.")
    assert len(latest_risk) > 0
    assert "current_risk_score" in latest_risk[0]
    
    # 5. Site Detail Risk
    site_risk = get_json(f"/api/v1/risk/{sample_site_id}")
    print(f"5. GET /api/v1/risk/{sample_site_id} -> Score: {site_risk['current_risk_score']} / Level: {site_risk['current_risk_level']}")
    assert site_risk["site_id"] == sample_site_id
    
    # 6. Timeseries (with date filter)
    ts = get_json(f"/api/v1/risk/{sample_site_id}/timeseries?start_date=2025-05-01&end_date=2025-06-01")
    print(f"6. GET /api/v1/risk/{sample_site_id}/timeseries -> Returned {len(ts)} historical observations.")
    
    # 7. Environment
    env = get_json(f"/api/v1/environment/{sample_site_id}")
    print(f"7. GET /api/v1/environment/{sample_site_id} -> Trigger Score: {env['dynamic_trigger_score']}, Status: {env['data_status']}")
    
    # 8. Susceptibility
    sus = get_json(f"/api/v1/susceptibility/{sample_site_id}")
    print(f"8. GET /api/v1/susceptibility/{sample_site_id} -> Static Susceptibility Score: {sus['static_susceptibility_score']}")
    
    # 9. Explanation
    exp = get_json(f"/api/v1/explanation/{sample_site_id}")
    print(f"9. GET /api/v1/explanation/{sample_site_id} -> Explanation: {exp['risk_explanation'][:80]}...")
    
    # 10. Map GeoJSON Risk
    map_geojson = get_json("/api/v1/map/risk")
    print(f"10. GET /api/v1/map/risk -> Type: {map_geojson['type']}, Features: {len(map_geojson['features'])}")
    assert map_geojson["type"] == "FeatureCollection"
    coords = map_geojson["features"][0]["geometry"]["coordinates"]
    print(f"    Sample Feature Coordinates [lon, lat]: {coords}")
    assert 87.0 <= coords[0] <= 98.0  # lon
    assert 21.0 <= coords[1] <= 30.0  # lat
    
    # 11. Demo Simulation POST
    sim_req = {
        "site_id": sample_site_id,
        "simulated_rainfall_1d": 150.0,
        "simulated_rainfall_3d": 280.0,
        "simulated_rainfall_7d": 450.0,
        "simulated_soil_moisture": 0.48,
        "scenario_name": "Heavy Monsoon Downpour Verification"
    }
    sim_res = post_json("/api/v1/demo/simulate", sim_req)
    print(f"11. POST /api/v1/demo/simulate -> Simulated Score: {sim_res['simulated_current_risk_score']} ({sim_res['simulated_current_risk_level']})")
    assert sim_res["simulation_mode"] is True
    assert sim_res["data_source"] == "SIMULATED_DEMO"
    
    print("\nALL 11 API ENDPOINTS VERIFIED LIVE SUCCESSFULLY!")

if __name__ == "__main__":
    run_live_tests()
