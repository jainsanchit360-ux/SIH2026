import React from 'react';
import { Layers, Zap, ShieldAlert, Equal } from 'lucide-react';

const RiskLayerComparison = ({ record }) => {
  const staticScore = record?.static_susceptibility_score !== null && record?.static_susceptibility_score !== undefined
    ? Math.round(record.static_susceptibility_score)
    : 'N/A';
  const triggerScore = record?.dynamic_trigger_score !== null && record?.dynamic_trigger_score !== undefined
    ? Math.round(record.dynamic_trigger_score)
    : 'N/A';
  const riskScore = record?.current_risk_score !== null && record?.current_risk_score !== undefined
    ? Math.round(record.current_risk_score)
    : 'N/A';

  return (
    <div className="panel-card">
      <h3 className="panel-title">
        <Layers size={16} color="var(--accent-cyan)" />
        TWO-LAYER OPERATIONAL RISK ARCHITECTURE
      </h3>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr auto 1fr', gap: '0.5rem', alignItems: 'center', margin: '0.75rem 0' }}>
        {/* Layer 1 */}
        <div style={{
          backgroundColor: 'var(--bg-dark)',
          border: '1px solid var(--bg-border)',
          borderRadius: '6px',
          padding: '0.75rem',
          textAlign: 'center',
        }}>
          <span style={{ fontSize: '0.7rem', fontWeight: '700', color: 'var(--accent-blue)', textTransform: 'uppercase' }}>
            LAYER 1: STATIC
          </span>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: '0.2rem 0' }}>Terrain Predisposition</p>
          <div style={{ fontSize: '1.25rem', fontWeight: '800', color: '#ffffff' }}>
            {staticScore} <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>/ 100</span>
          </div>
          <span style={{ fontSize: '0.68rem', color: 'var(--text-sub)' }}>Weight: 55%</span>
        </div>

        <div style={{ color: 'var(--text-muted)', fontWeight: '700' }}>+</div>

        {/* Layer 2 */}
        <div style={{
          backgroundColor: 'var(--bg-dark)',
          border: '1px solid var(--bg-border)',
          borderRadius: '6px',
          padding: '0.75rem',
          textAlign: 'center',
        }}>
          <span style={{ fontSize: '0.7rem', fontWeight: '700', color: 'var(--accent-cyan)', textTransform: 'uppercase' }}>
            LAYER 2: DYNAMIC
          </span>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: '0.2rem 0' }}>Rainfall + Soil Pressure</p>
          <div style={{ fontSize: '1.25rem', fontWeight: '800', color: '#ffffff' }}>
            {triggerScore} <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>/ 100</span>
          </div>
          <span style={{ fontSize: '0.68rem', color: 'var(--text-sub)' }}>Weight: 45%</span>
        </div>

        <div style={{ color: 'var(--accent-cyan)', fontWeight: '700' }}>=</div>

        {/* Fused Risk */}
        <div style={{
          backgroundColor: 'rgba(56, 189, 248, 0.1)',
          border: '1px solid rgba(56, 189, 248, 0.3)',
          borderRadius: '6px',
          padding: '0.75rem',
          textAlign: 'center',
        }}>
          <span style={{ fontSize: '0.7rem', fontWeight: '700', color: '#ffffff', textTransform: 'uppercase' }}>
            FUSED CURRENT RISK
          </span>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-sub)', margin: '0.2rem 0' }}>Prototype Index</p>
          <div style={{ fontSize: '1.25rem', fontWeight: '900', color: 'var(--accent-cyan)' }}>
            {riskScore} <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>/ 100</span>
          </div>
          <span style={{ fontSize: '0.68rem', color: 'var(--text-sub)' }}>Operational Score</span>
        </div>
      </div>

      <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: 1.4, marginTop: '0.5rem' }}>
        <strong>Scientific Note:</strong> Static susceptibility models spatial terrain vulnerability using ML (Phase 5b). Dynamic trigger measures short-term antecedent hydrometeorological pressure. The fused score is a operational index [0–100], not an absolute probability.
      </p>
    </div>
  );
};

export default RiskLayerComparison;
