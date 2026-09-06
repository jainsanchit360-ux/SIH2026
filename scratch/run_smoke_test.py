import pandas as pd
import json
from pathlib import Path
from src.risk.susceptibility import StaticSusceptibilityEngine
from src.risk.trigger_engine import DynamicTriggerEngine
from src.risk.risk_fusion import RiskFusionEngine
from src.risk.demo_simulation import simulate_dynamic_risk_scenario

def run_smoke_test():
    risk_df = pd.read_parquet(Path(r"d:\downloads\sih 26001\data\processed\current_landslide_risk.parquet"))
    pilot_row = risk_df.iloc[0].to_dict()

    print("=== STEP 8: END-TO-END SMOKE TEST ===")
    print("1. Real Location Record Loaded:")
    site_id = pilot_row.get("site_id")
    site_name = pilot_row.get("site_name")
    state = pilot_row.get("state")
    lat = pilot_row.get("latitude")
    lon = pilot_row.get("longitude")
    obs_date = pilot_row.get("observation_date")
    print(f"   Site ID: {site_id}, Name: {site_name}, State: {state}")
    print(f"   Coords: ({lat}, {lon}), Date: {obs_date}")

    # Static Susceptibility
    sus_engine = StaticSusceptibilityEngine()
    static_res = sus_engine.evaluate_static_susceptibility(
        latitude=float(lat),
        longitude=float(lon),
        elevation_m=float(pilot_row.get("elevation_m", 1250.0)),
        slope_deg=float(pilot_row.get("slope_deg", 28.5)),
        historical_count_5km=float(pilot_row.get("historical_count_5km", 4.0)),
        historical_count_10km=float(pilot_row.get("historical_count_10km", 12.0)),
    )
    print("\n2. Static Susceptibility Output:")
    print(f"   Score: {static_res.get('static_susceptibility_score')} / 100")
    print(f"   Level: {static_res.get('static_susceptibility_level')}")
    print(f"   Factors: {static_res.get('static_major_factors')}")

    # Dynamic Trigger
    trig_engine = DynamicTriggerEngine()
    dyn_res = trig_engine.calculate_trigger(
        rainfall_1d=float(pilot_row.get("rainfall_1d", 45.0)),
        rainfall_3d=float(pilot_row.get("rainfall_3d", 110.0)),
        rainfall_7d=float(pilot_row.get("rainfall_7d", 180.0)),
        soil_moisture=float(pilot_row.get("soil_moisture", 0.35)),
        observation_date=str(obs_date),
    )
    print("\n3. Dynamic Trigger Output:")
    print(f"   Score: {dyn_res.get('dynamic_trigger_score')} / 100")
    print(f"   Level: {dyn_res.get('dynamic_trigger_level')}")
    print(f"   Factors: {dyn_res.get('major_trigger_factors')}")

    # Risk Fusion
    fusion_engine = RiskFusionEngine()
    fused_res = fusion_engine.fuse(static_res, dyn_res)
    print("\n4. Fused Current Landslide Risk Output (REAL DATA):")
    print(f"   Current Risk Score: {fused_res.get('current_risk_score')} / 100")
    print(f"   Current Risk Level: {fused_res.get('current_risk_level')}")
    print(f"   Explanation: {fused_res.get('risk_explanation')}")
    print(f"   Data Source: {fused_res.get('data_source', 'REAL_OBSERVED_PROCESSED')}")
    print(f"   Calibration Disclaimer: {fused_res.get('calibration_disclaimer')}")

    # Demo Simulation
    sim_res = simulate_dynamic_risk_scenario(
        baseline_location_record={**pilot_row, "elevation_m": 1250.0, "slope_deg": 28.5, "historical_count_5km": 4.0, "historical_count_10km": 12.0},
        simulated_rainfall_1d=120.0,
        simulated_rainfall_3d=220.0,
        simulated_rainfall_7d=350.0,
        simulated_soil_moisture=0.45,
        scenario_name="Extreme Monsoon Downpour Simulation"
    )
    print("\n5. Demo Simulation Output (SIMULATED DATA):")
    print(f"   Scenario: {sim_res.get('scenario_name')}")
    print(f"   Simulated Current Risk Score: {sim_res.get('current_risk_score')} / 100")
    print(f"   Simulated Risk Level: {sim_res.get('current_risk_level')}")
    print(f"   Simulation Mode Flag: {sim_res.get('simulation_mode')}")
    print(f"   Data Source: {sim_res.get('data_source')}")
    print(f"   Explanation: {sim_res.get('risk_explanation')}")

    assert 0 <= fused_res['current_risk_score'] <= 100
    assert 0 <= sim_res['current_risk_score'] <= 100
    assert sim_res['data_source'] == 'SIMULATED_DEMO'
    print("\nSMOKE TEST COMPLETED SUCCESSFULLY! All scores bounded [0, 100], flags verified.")

if __name__ == "__main__":
    run_smoke_test()
