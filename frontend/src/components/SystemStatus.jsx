import React from 'react';
import { Server, Database, Cpu, CheckCircle2, ShieldCheck } from 'lucide-react';

const SystemStatus = ({ systemStatus }) => {
  if (!systemStatus) return null;

  const records = systemStatus.dataset_records || {};

  return (
    <div className="panel-card">
      <h3 className="panel-title">
        <Server size={16} color="var(--accent-cyan)" />
        SYSTEM HEALTH & DATASET METRICS
      </h3>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', fontSize: '0.78rem' }}>
        <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.65rem', borderRadius: '6px', border: '1px solid var(--bg-border)' }}>
          <span style={{ color: 'var(--text-muted)' }}>Service Status:</span>
          <div style={{ fontWeight: '700', color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.3rem', marginTop: '0.2rem' }}>
            <CheckCircle2 size={14} /> {systemStatus.service_status}
          </div>
        </div>

        <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.65rem', borderRadius: '6px', border: '1px solid var(--bg-border)' }}>
          <span style={{ color: 'var(--text-muted)' }}>Model Status:</span>
          <div style={{ fontWeight: '700', color: '#ffffff', display: 'flex', alignItems: 'center', gap: '0.3rem', marginTop: '0.2rem' }}>
            <Cpu size={14} color="var(--accent-cyan)" /> {systemStatus.model_status} (v{systemStatus.model_version})
          </div>
        </div>

        <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.65rem', borderRadius: '6px', border: '1px solid var(--bg-border)' }}>
          <span style={{ color: 'var(--text-muted)' }}>Environmental Dataset:</span>
          <div style={{ fontWeight: '700', color: 'var(--text-sub)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginTop: '0.2rem' }}>
            <Database size={14} /> {systemStatus.environmental_dataset_status}
          </div>
        </div>

        <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.65rem', borderRadius: '6px', border: '1px solid var(--bg-border)' }}>
          <span style={{ color: 'var(--text-muted)' }}>Cached Records:</span>
          <div style={{ fontWeight: '700', color: '#ffffff', marginTop: '0.2rem' }}>
            Risk: {records.current_landslide_risk || 1440} | Env: {records.dynamic_environmental_features || 1440}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemStatus;
