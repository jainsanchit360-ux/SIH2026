import React, { useState } from 'react';
import { Sliders, Play, AlertOctagon, RotateCcw, ArrowRight, BellRing } from 'lucide-react';
import { simulateAndAlert } from '../api/client';

const DemoSimulationPanel = ({ selectedSite, onSimulationComplete }) => {
  const [rainfall1d, setRainfall1d] = useState(85);
  const [rainfall3d, setRainfall3d] = useState(160);
  const [rainfall7d, setRainfall7d] = useState(260);
  const [soilMoisture, setSoilMoisture] = useState(42);
  const [scenarioName, setScenarioName] = useState('Heavy Monsoon Cloudburst Scenario');

  const [simulationResult, setSimulationResult] = useState(null);
  const [simulating, setSimulating] = useState(false);
  const [simError, setSimError] = useState(null);

  const handleRunSimulation = async (e) => {
    e.preventDefault();
    setSimulating(true);
    setSimError(null);

    try {
      const payload = {
        site_id: selectedSite?.site_id || 'GSI_SITE_01',
        simulated_rainfall_1d: parseFloat(rainfall1d),
        simulated_rainfall_3d: parseFloat(rainfall3d),
        simulated_rainfall_7d: parseFloat(rainfall7d),
        simulated_soil_moisture: parseFloat(soilMoisture) / 100.0, // Convert percentage to fraction
        scenario_name: scenarioName,
      };

      const res = await simulateAndAlert(payload);
      setSimulationResult(res);
      if (onSimulationComplete) {
        onSimulationComplete(res);
      }
    } catch (err) {
      console.error('Demo simulation error:', err);
      setSimError('Failed to execute simulation. Verify parameter ranges.');
    } finally {
      setSimulating(false);
    }
  };

  const handleReset = () => {
    setSimulationResult(null);
    setSimError(null);
  };

  return (
    <div className="panel-card" style={{ border: '1px dashed var(--accent-cyan)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <h3 className="panel-title" style={{ margin: 0 }}>
          <Sliders size={16} color="var(--accent-cyan)" />
          WHAT-IF DEMO RISK SIMULATOR
        </h3>
        <span className="badge badge-moderate" style={{ fontSize: '0.7rem' }}>
          SIMULATED DEMO ONLY
        </span>
      </div>

      <p style={{ fontSize: '0.78rem', color: 'var(--text-sub)', marginBottom: '1rem' }}>
        Simulate custom environmental pressure scenarios for <strong>{selectedSite?.site_name || 'Pilot Location'}</strong> without mutating baseline historical records.
      </p>

      <form onSubmit={handleRunSimulation} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {/* Scenario Label */}
        <div>
          <label style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.2rem' }}>
            Scenario Title:
          </label>
          <input
            type="text"
            value={scenarioName}
            onChange={(e) => setScenarioName(e.target.value)}
            style={{
              width: '100%',
              padding: '0.4rem 0.65rem',
              backgroundColor: 'var(--bg-dark)',
              border: '1px solid var(--bg-border)',
              borderRadius: '4px',
              color: '#ffffff',
              fontSize: '0.8rem',
            }}
          />
        </div>

        {/* Sliders Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <div>
            <label style={{ fontSize: '0.72rem', color: 'var(--text-sub)', display: 'flex', justifyContent: 'space-between' }}>
              <span>24h Rainfall:</span>
              <strong style={{ color: 'var(--accent-cyan)' }}>{rainfall1d} mm/day</strong>
            </label>
            <input
              type="range"
              min="0"
              max="300"
              value={rainfall1d}
              onChange={(e) => setRainfall1d(e.target.value)}
              style={{ width: '100%', cursor: 'pointer' }}
            />
          </div>

          <div>
            <label style={{ fontSize: '0.72rem', color: 'var(--text-sub)', display: 'flex', justifyContent: 'space-between' }}>
              <span>3-Day Rainfall:</span>
              <strong style={{ color: 'var(--accent-cyan)' }}>{rainfall3d} mm</strong>
            </label>
            <input
              type="range"
              min="0"
              max="600"
              value={rainfall3d}
              onChange={(e) => setRainfall3d(e.target.value)}
              style={{ width: '100%', cursor: 'pointer' }}
            />
          </div>

          <div>
            <label style={{ fontSize: '0.72rem', color: 'var(--text-sub)', display: 'flex', justifyContent: 'space-between' }}>
              <span>7-Day Rainfall:</span>
              <strong style={{ color: 'var(--accent-cyan)' }}>{rainfall7d} mm</strong>
            </label>
            <input
              type="range"
              min="0"
              max="1200"
              value={rainfall7d}
              onChange={(e) => setRainfall7d(e.target.value)}
              style={{ width: '100%', cursor: 'pointer' }}
            />
          </div>

          <div>
            <label style={{ fontSize: '0.72rem', color: 'var(--text-sub)', display: 'flex', justifyContent: 'space-between' }}>
              <span>Soil Moisture:</span>
              <strong style={{ color: 'var(--accent-cyan)' }}>{soilMoisture}%</strong>
            </label>
            <input
              type="range"
              min="5"
              max="95"
              value={soilMoisture}
              onChange={(e) => setSoilMoisture(e.target.value)}
              style={{ width: '100%', cursor: 'pointer' }}
            />
          </div>
        </div>

        {/* Simulation Trigger Button */}
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
          <button type="submit" disabled={simulating} className="btn-primary" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem' }}>
            <Play size={14} />
            {simulating ? 'Calculating Simulation...' : 'Execute What-If Scenario'}
          </button>
          {simulationResult && (
            <button type="button" onClick={handleReset} className="btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <RotateCcw size={14} /> Reset
            </button>
          )}
        </div>
      </form>

      {simError && (
        <div style={{ color: 'var(--risk-high)', fontSize: '0.75rem', marginTop: '0.5rem' }}>
          {simError}
        </div>
      )}

      {/* Simulation Result Output */}
      {simulationResult && (
        <div style={{
          marginTop: '1rem',
          padding: '0.85rem',
          backgroundColor: 'rgba(56, 189, 248, 0.08)',
          border: '1px solid var(--accent-cyan)',
          borderRadius: '6px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <strong style={{ fontSize: '0.82rem', color: '#ffffff' }}>SIMULATION RESULT COMPARISON</strong>
            <span className="badge badge-high" style={{ fontSize: '0.68rem' }}>
              {simulationResult.simulated_current_risk_level}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-around', margin: '0.5rem 0' }}>
            {/* Baseline */}
            <div style={{ textAlign: 'center' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Baseline Risk</span>
              <div style={{ fontSize: '1.2rem', fontWeight: '800', color: 'var(--text-sub)' }}>
                {simulationResult.baseline_current_risk_score !== null ? Math.round(simulationResult.baseline_current_risk_score) : 'N/A'}
              </div>
            </div>

            <ArrowRight size={18} color="var(--accent-cyan)" />

            {/* Simulated */}
            <div style={{ textAlign: 'center' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-sub)', fontWeight: '700' }}>Simulated Risk</span>
              <div style={{ fontSize: '1.5rem', fontWeight: '900', color: 'var(--risk-high)' }}>
                {Math.round(simulationResult.simulated_current_risk_score)}
              </div>
            </div>
          </div>

          <p style={{ fontSize: '0.72rem', color: 'var(--text-sub)', marginTop: '0.4rem', borderTop: '1px solid var(--bg-border)', paddingTop: '0.4rem' }}>
            <strong style={{ color: '#ffffff' }}>Trigger Delta: </strong>
            Simulated dynamic trigger score reached <strong>{Math.round(simulationResult.dynamic_trigger_score)}/100</strong>.
          </p>

          {simulationResult.alert_generated ? (
            <div style={{
              marginTop: '0.5rem',
              padding: '0.4rem 0.65rem',
              backgroundColor: 'var(--risk-high-bg)',
              border: '1px solid var(--risk-high-border)',
              borderRadius: '4px',
              color: 'var(--risk-high)',
              fontSize: '0.74rem',
              fontWeight: '700',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}>
              <BellRing size={14} />
              <span>PROTOTYPE WARNING GENERATED: {simulationResult.alert?.alert_id} ({simulationResult.alert?.severity})</span>
            </div>
          ) : (
            <div style={{ marginTop: '0.5rem', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Risk level did not cross operational warning threshold (MODERATE or HIGH required).
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DemoSimulationPanel;
