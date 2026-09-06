import React from 'react';
import { ShieldAlert, Activity, Database, Server } from 'lucide-react';
import HeaderNavigation from './HeaderNavigation';

const Header = ({ systemStatus, isBackendConnected, activeTab, setActiveTab, unacknowledgedCount }) => {
  const status = systemStatus?.status || 'OPERATIONAL';
  const obsDate = systemStatus?.latest_valid_risk_observation_date || systemStatus?.last_available_observation_date || '2025-09-23';
  const modelVer = systemStatus?.model_version || '1.1.0-phase5b';

  return (
    <header style={{
      height: '64px',
      backgroundColor: 'var(--bg-panel)',
      borderBottom: '1px solid var(--bg-border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 1.5rem',
      zIndex: 100,
    }}>
      {/* Branding */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div style={{
          width: '36px',
          height: '36px',
          borderRadius: '8px',
          backgroundColor: 'rgba(56, 189, 248, 0.15)',
          border: '1px solid rgba(56, 189, 248, 0.3)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--accent-cyan)'
        }}>
          <ShieldAlert size={22} />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.2rem', fontWeight: '800', letterSpacing: '-0.02em', color: '#ffffff' }}>
              ResQtech
            </span>
            <span style={{
              fontSize: '0.7rem',
              fontWeight: '700',
              padding: '0.15rem 0.4rem',
              backgroundColor: 'rgba(59, 130, 246, 0.2)',
              color: 'var(--accent-cyan)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              borderRadius: '4px'
            }}>
              SIH26001
            </span>
          </div>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-sub)', fontWeight: '500' }}>
            Landslide Early Warning System · North-Eastern Region (NER) India
          </p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <HeaderNavigation
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        unacknowledgedCount={unacknowledgedCount}
      />

      {/* Center Metadata Badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          padding: '0.35rem 0.75rem',
          backgroundColor: 'rgba(245, 158, 11, 0.12)',
          border: '1px solid rgba(245, 158, 11, 0.3)',
          borderRadius: '6px',
          fontSize: '0.78rem',
          color: 'var(--risk-mod)'
        }}>
          <Database size={14} />
          <span>OFFLINE HISTORICAL PROTOTYPE DATA</span>
        </div>

        <div style={{
          fontSize: '0.78rem',
          color: 'var(--text-sub)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          backgroundColor: 'var(--bg-dark)',
          padding: '0.35rem 0.75rem',
          borderRadius: '6px',
          border: '1px solid var(--bg-border)'
        }}>
          <span style={{ color: 'var(--text-muted)' }}>Latest Observation:</span>
          <strong style={{ color: '#ffffff' }}>{obsDate}</strong>
        </div>
      </div>

      {/* Right Backend Health Indicators */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.78rem' }}>
          <Server size={14} color={isBackendConnected ? '#10b981' : '#ef4444'} />
          <span style={{ color: 'var(--text-sub)' }}>API:</span>
          <span className={`badge ${isBackendConnected ? 'badge-low' : 'badge-high'}`}>
            {isBackendConnected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem' }}>
          <Activity size={14} color="var(--accent-cyan)" />
          <span style={{ color: 'var(--text-sub)' }}>Model:</span>
          <span style={{ color: '#ffffff', fontWeight: '600' }}>v{modelVer}</span>
        </div>
      </div>
    </header>
  );
};

export default Header;
