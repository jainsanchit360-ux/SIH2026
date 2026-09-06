import React from 'react';
import { HelpCircle, AlertCircle, TrendingUp, TrendingDown, Minus, ChevronRight } from 'lucide-react';

const ExplainabilityPanel = ({ explanation, loading }) => {
  if (loading) {
    return (
      <div className="panel-card" style={{ minHeight: '200px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--text-sub)', fontSize: '0.85rem' }}>Loading explainability narrative...</p>
      </div>
    );
  }

  if (!explanation) {
    return (
      <div className="panel-card">
        <h3 className="panel-title">
          <HelpCircle size={16} color="var(--accent-cyan)" />
          EXPLAINABILITY & WHAT-CHANGED NARRATIVE
        </h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
          Select a monitored location to inspect why it is at risk and view key contributor factors.
        </p>
      </div>
    );
  }

  const {
    site_name,
    current_risk_score,
    current_risk_level,
    previous_risk_score,
    risk_score_change,
    risk_trend,
    major_risk_factors = [],
    static_contributors = [],
    dynamic_contributors = [],
    risk_explanation,
    what_changed,
  } = explanation;

  const trendIcon =
    risk_trend === 'INCREASING' ? <TrendingUp size={16} color="var(--risk-high)" /> :
    risk_trend === 'DECREASING' ? <TrendingDown size={16} color="var(--risk-low)" /> :
    <Minus size={16} color="var(--text-muted)" />;

  return (
    <div className="panel-card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h3 className="panel-title" style={{ margin: 0 }}>
          <HelpCircle size={16} color="var(--accent-cyan)" />
          WHY IS THIS LOCATION AT RISK?
        </h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', color: 'var(--text-sub)' }}>
          <span>Trend:</span>
          {trendIcon}
          <strong style={{ color: '#ffffff' }}>{risk_trend || 'STABLE'}</strong>
          {risk_score_change !== null && risk_score_change !== undefined && (
            <span style={{ fontSize: '0.72rem', color: risk_score_change > 0 ? 'var(--risk-high)' : 'var(--risk-low)' }}>
              ({risk_score_change > 0 ? `+${risk_score_change.toFixed(1)}` : risk_score_change.toFixed(1)})
            </span>
          )}
        </div>
      </div>

      {/* Main Narrative Paragraph */}
      <div style={{
        backgroundColor: 'var(--bg-dark)',
        border: '1px solid var(--bg-border)',
        borderRadius: '6px',
        padding: '0.85rem',
        fontSize: '0.83rem',
        color: 'var(--text-main)',
        lineHeight: 1.5,
        marginBottom: '1rem',
      }}>
        <p style={{ fontWeight: '600', color: '#ffffff', marginBottom: '0.35rem' }}>
          {risk_explanation || 'Location risk level evaluated by fused static susceptibility and dynamic trigger engines.'}
        </p>
        {what_changed && (
          <p style={{ color: 'var(--text-sub)', fontSize: '0.78rem', marginTop: '0.4rem', borderTop: '1px solid var(--bg-border)', paddingTop: '0.4rem' }}>
            <strong style={{ color: 'var(--accent-cyan)' }}>What Changed: </strong> {what_changed}
          </p>
        )}
      </div>

      {/* Major Risk Factors Tags */}
      {major_risk_factors.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-sub)', textTransform: 'uppercase' }}>
            Primary Drivers:
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.4rem' }}>
            {major_risk_factors.map((factor, idx) => (
              <span
                key={idx}
                style={{
                  fontSize: '0.72rem',
                  padding: '0.2rem 0.55rem',
                  backgroundColor: 'rgba(56, 189, 248, 0.12)',
                  color: 'var(--accent-cyan)',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  borderRadius: '4px',
                  fontWeight: '600',
                }}
              >
                {factor}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Contributors Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.78rem' }}>
        {/* Static Contributors */}
        <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.65rem', borderRadius: '6px', border: '1px solid var(--bg-border)' }}>
          <span style={{ fontWeight: '700', color: 'var(--text-sub)', display: 'flex', alignItems: 'center', gap: '0.2rem', marginBottom: '0.35rem' }}>
            <ChevronRight size={13} color="var(--accent-blue)" /> Static Predisposition
          </span>
          {static_contributors.length > 0 ? (
            <ul style={{ paddingLeft: '1.1rem', color: 'var(--text-muted)' }}>
              {static_contributors.map((c, i) => <li key={i} style={{ marginBottom: '0.15rem' }}>{c}</li>)}
            </ul>
          ) : (
            <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>Standard NER terrain profile</span>
          )}
        </div>

        {/* Dynamic Contributors */}
        <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.65rem', borderRadius: '6px', border: '1px solid var(--bg-border)' }}>
          <span style={{ fontWeight: '700', color: 'var(--text-sub)', display: 'flex', alignItems: 'center', gap: '0.2rem', marginBottom: '0.35rem' }}>
            <ChevronRight size={13} color="var(--accent-cyan)" /> Dynamic Trigger Factors
          </span>
          {dynamic_contributors.length > 0 ? (
            <ul style={{ paddingLeft: '1.1rem', color: 'var(--text-muted)' }}>
              {dynamic_contributors.map((c, i) => <li key={i} style={{ marginBottom: '0.15rem' }}>{c}</li>)}
            </ul>
          ) : (
            <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>Baseline environmental pressure</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default ExplainabilityPanel;
