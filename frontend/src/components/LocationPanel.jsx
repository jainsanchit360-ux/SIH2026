import React from 'react';
import { MapPin, Calendar, Compass, Mountain, History, AlertTriangle, Layers, Zap } from 'lucide-react';
import EnvironmentalCards from './EnvironmentalCards';

const LocationPanel = ({ riskRecord, loading, error }) => {
  if (loading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-sub)' }}>
        <p>Loading location intelligence data...</p>
      </div>
    );
  }

  if (error || !riskRecord) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        <AlertTriangle size={32} color="var(--text-muted)" style={{ marginBottom: '0.5rem' }} />
        <p style={{ color: 'var(--text-sub)', fontWeight: '600' }}>Select a monitored location from the map or dropdown to inspect intelligence metrics.</p>
      </div>
    );
  }

  const riskLevel = riskRecord.current_risk_level || 'INSUFFICIENT_DATA';
  const riskScore = riskRecord.current_risk_score !== null && riskRecord.current_risk_score !== undefined
    ? Math.round(riskRecord.current_risk_score)
    : 'N/A';

  const badgeClass =
    riskLevel === 'HIGH' ? 'badge-high' :
    riskLevel === 'MODERATE' ? 'badge-moderate' :
    riskLevel === 'LOW' ? 'badge-low' : 'badge-nodata';

  return (
    <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Site Header */}
      <div>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
          <h2 style={{ fontSize: '1.15rem', fontWeight: '800', color: '#ffffff', lineHeight: 1.3 }}>
            {riskRecord.site_name}
          </h2>
          <span className={`badge ${badgeClass}`}>
            {riskLevel}
          </span>
        </div>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-sub)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <MapPin size={13} color="var(--accent-cyan)" />
          {riskRecord.district}, {riskRecord.state} · Lat {riskRecord.latitude?.toFixed(2)}°N, Lon {riskRecord.longitude?.toFixed(2)}°E
        </p>
        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.35rem', marginTop: '0.25rem' }}>
          <Calendar size={13} />
          Observation Date: <strong style={{ color: '#ffffff' }}>{riskRecord.observation_date || 'N/A'}</strong>
        </p>
      </div>

      {/* Main Fused Current Risk Index Card */}
      <div className="panel-card" style={{
        background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9))',
        border: '1px solid var(--bg-border)',
        position: 'relative',
        overflow: 'hidden',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-sub)' }}>
            CURRENT LANDSLIDE RISK INDEX
          </span>
          <Zap size={16} color="var(--accent-cyan)" />
        </div>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
          <span style={{ fontSize: '2.5rem', fontWeight: '900', color: '#ffffff', lineHeight: 1 }}>
            {riskScore}
          </span>
          <span style={{ fontSize: '1rem', color: 'var(--text-muted)', fontWeight: '700' }}>/ 100</span>
        </div>

        {/* Progress Bar */}
        <div style={{
          height: '6px',
          backgroundColor: 'var(--bg-dark)',
          borderRadius: '3px',
          marginTop: '0.75rem',
          overflow: 'hidden'
        }}>
          <div style={{
            height: '100%',
            width: typeof riskScore === 'number' ? `${Math.min(100, Math.max(0, riskScore))}%` : '0%',
            backgroundColor:
              riskLevel === 'HIGH' ? 'var(--risk-high)' :
              riskLevel === 'MODERATE' ? 'var(--risk-mod)' :
              riskLevel === 'LOW' ? 'var(--risk-low)' : 'var(--risk-nodata)',
            transition: 'width 0.5s ease',
          }} />
        </div>
      </div>

      {/* Two-Layer Breakdown Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
        {/* Layer 1: Static Susceptibility */}
        <div style={{
          backgroundColor: 'var(--bg-dark)',
          border: '1px solid var(--bg-border)',
          borderRadius: '6px',
          padding: '0.85rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.72rem', color: 'var(--text-sub)', fontWeight: '700', textTransform: 'uppercase' }}>
            <Layers size={13} color="var(--accent-blue)" />
            <span>STATIC SUSCEPTIBILITY</span>
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#ffffff', marginTop: '0.35rem' }}>
            {riskRecord.static_susceptibility_score !== null ? Math.round(riskRecord.static_susceptibility_score) : 'N/A'}
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '500' }}> / 100</span>
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-sub)', fontWeight: '600' }}>
            Level: {riskRecord.static_susceptibility_level || 'N/A'}
          </span>
        </div>

        {/* Layer 2: Dynamic Trigger */}
        <div style={{
          backgroundColor: 'var(--bg-dark)',
          border: '1px solid var(--bg-border)',
          borderRadius: '6px',
          padding: '0.85rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.72rem', color: 'var(--text-sub)', fontWeight: '700', textTransform: 'uppercase' }}>
            <Zap size={13} color="var(--accent-cyan)" />
            <span>DYNAMIC TRIGGER</span>
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#ffffff', marginTop: '0.35rem' }}>
            {riskRecord.dynamic_trigger_score !== null && riskRecord.dynamic_trigger_score !== undefined ? Math.round(riskRecord.dynamic_trigger_score) : 'N/A'}
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '500' }}> / 100</span>
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-sub)', fontWeight: '600' }}>
            Level: {riskRecord.dynamic_trigger_level || 'N/A'}
          </span>
        </div>
      </div>

      {/* Environmental Indicators */}
      <EnvironmentalCards record={riskRecord} />

      {/* Terrain & Historical Predisposition */}
      <div style={{
        backgroundColor: 'var(--bg-dark)',
        border: '1px solid var(--bg-border)',
        borderRadius: '6px',
        padding: '0.85rem'
      }}>
        <h4 style={{ fontSize: '0.78rem', fontWeight: '700', color: 'var(--text-sub)', uppercase: 'true', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Mountain size={14} color="var(--text-sub)" />
          TERRAIN & HISTORICAL PREDISPOSITION
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.78rem' }}>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>Elevation: </span>
            <strong style={{ color: '#ffffff' }}>{riskRecord.elevation_m !== null ? `${Math.round(riskRecord.elevation_m)} m` : 'N/A'}</strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>Slope: </span>
            <strong style={{ color: '#ffffff' }}>{riskRecord.slope_deg !== null ? `${riskRecord.slope_deg.toFixed(1)}°` : 'N/A'}</strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>GSI Landslides (5km): </span>
            <strong style={{ color: '#ffffff' }}>{riskRecord.historical_count_5km !== null ? Math.round(riskRecord.historical_count_5km) : 'N/A'}</strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>GSI Landslides (10km): </span>
            <strong style={{ color: '#ffffff' }}>{riskRecord.historical_count_10km !== null ? Math.round(riskRecord.historical_count_10km) : 'N/A'}</strong>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LocationPanel;
