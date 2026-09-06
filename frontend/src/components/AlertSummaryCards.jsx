import React from 'react';
import { ShieldAlert, AlertTriangle, CheckCircle, Truck, Info, Sliders } from 'lucide-react';

const AlertSummaryCards = ({ summary }) => {
  if (!summary) return null;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
      {/* Active Warnings */}
      <div style={{
        backgroundColor: 'var(--bg-panel)',
        border: '1px solid var(--risk-high-border)',
        borderRadius: '8px',
        padding: '1rem',
        background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(17, 24, 39, 0.9))',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-sub)', textTransform: 'uppercase' }}>
            ACTIVE WARNINGS
          </span>
          <ShieldAlert size={16} color="var(--risk-high)" />
        </div>
        <div style={{ fontSize: '1.8rem', fontWeight: '900', color: '#ffffff' }}>
          {summary.active_warnings_count}
        </div>
        <span style={{ fontSize: '0.68rem', color: 'var(--risk-high)', fontWeight: '600' }}>
          Require Attention
        </span>
      </div>

      {/* Unacknowledged Alerts */}
      <div style={{
        backgroundColor: 'var(--bg-panel)',
        border: '1px solid var(--risk-mod-border)',
        borderRadius: '8px',
        padding: '1rem',
        background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(17, 24, 39, 0.9))',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-sub)', textTransform: 'uppercase' }}>
            UNACKNOWLEDGED
          </span>
          <AlertTriangle size={16} color="var(--risk-mod)" />
        </div>
        <div style={{ fontSize: '1.8rem', fontWeight: '900', color: '#ffffff' }}>
          {summary.unacknowledged_alerts_count}
        </div>
        <span style={{ fontSize: '0.68rem', color: 'var(--risk-mod)', fontWeight: '600' }}>
          New Alerts Pending
        </span>
      </div>

      {/* High-Risk Sites */}
      <div style={{
        backgroundColor: 'var(--bg-panel)',
        border: '1px solid var(--bg-border)',
        borderRadius: '8px',
        padding: '1rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-sub)', textTransform: 'uppercase' }}>
            HIGH-RISK SITES
          </span>
          <ShieldAlert size={16} color="var(--risk-high)" />
        </div>
        <div style={{ fontSize: '1.8rem', fontWeight: '900', color: '#ffffff' }}>
          {summary.high_risk_sites_count}
        </div>
        <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
          Risk Score ≥ 70
        </span>
      </div>

      {/* Response Dispatched */}
      <div style={{
        backgroundColor: 'var(--bg-panel)',
        border: '1px solid var(--bg-border)',
        borderRadius: '8px',
        padding: '1rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-sub)', textTransform: 'uppercase' }}>
            RESPONSE DISPATCHED
          </span>
          <Truck size={16} color="var(--accent-cyan)" />
        </div>
        <div style={{ fontSize: '1.8rem', fontWeight: '900', color: '#ffffff' }}>
          {summary.response_dispatched_count}
        </div>
        <span style={{ fontSize: '0.68rem', color: 'var(--accent-cyan)', fontWeight: '600' }}>
          Field Action In Progress
        </span>
      </div>

      {/* Demo Simulations */}
      <div style={{
        backgroundColor: 'var(--bg-panel)',
        border: '1px solid var(--bg-border)',
        borderRadius: '8px',
        padding: '1rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-sub)', textTransform: 'uppercase' }}>
            DEMO ALERTS
          </span>
          <Sliders size={16} color="var(--accent-cyan)" />
        </div>
        <div style={{ fontSize: '1.8rem', fontWeight: '900', color: '#ffffff' }}>
          {summary.simulated_alerts_count}
        </div>
        <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
          Simulated Scenarios
        </span>
      </div>
    </div>
  );
};

export default AlertSummaryCards;
