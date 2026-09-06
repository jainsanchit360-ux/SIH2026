import React from 'react';
import { Map, ShieldAlert, Bell, Activity } from 'lucide-react';

const HeaderNavigation = ({ activeTab, setActiveTab, unacknowledgedCount }) => {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem',
      backgroundColor: 'var(--bg-dark)',
      padding: '0.25rem',
      borderRadius: '8px',
      border: '1px solid var(--bg-border)',
    }}>
      {/* Tab 1: GIS Map Monitoring */}
      <button
        onClick={() => setActiveTab('MAP')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          padding: '0.45rem 0.9rem',
          borderRadius: '6px',
          border: 'none',
          backgroundColor: activeTab === 'MAP' ? 'var(--bg-panel-header)' : 'transparent',
          color: activeTab === 'MAP' ? '#ffffff' : 'var(--text-sub)',
          fontWeight: activeTab === 'MAP' ? '700' : '600',
          fontSize: '0.78rem',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
        }}
      >
        <Map size={14} color={activeTab === 'MAP' ? 'var(--accent-cyan)' : 'var(--text-muted)'} />
        <span>GIS MAP MONITORING</span>
      </button>

      {/* Tab 2: Authority Command Center */}
      <button
        onClick={() => setActiveTab('COMMAND_CENTER')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          padding: '0.45rem 0.9rem',
          borderRadius: '6px',
          border: 'none',
          backgroundColor: activeTab === 'COMMAND_CENTER' ? 'var(--bg-panel-header)' : 'transparent',
          color: activeTab === 'COMMAND_CENTER' ? '#ffffff' : 'var(--text-sub)',
          fontWeight: activeTab === 'COMMAND_CENTER' ? '700' : '600',
          fontSize: '0.78rem',
          cursor: 'pointer',
          position: 'relative',
          transition: 'all 0.2s ease',
        }}
      >
        <ShieldAlert size={14} color={activeTab === 'COMMAND_CENTER' ? 'var(--risk-high)' : 'var(--text-muted)'} />
        <span>AUTHORITY COMMAND CENTER</span>

        {unacknowledgedCount > 0 && (
          <span style={{
            backgroundColor: 'var(--risk-high)',
            color: '#ffffff',
            fontSize: '0.65rem',
            fontWeight: '800',
            padding: '0.1rem 0.4rem',
            borderRadius: '10px',
            marginLeft: '0.2rem',
          }}>
            {unacknowledgedCount}
          </span>
        )}
      </button>
    </div>
  );
};

export default HeaderNavigation;
