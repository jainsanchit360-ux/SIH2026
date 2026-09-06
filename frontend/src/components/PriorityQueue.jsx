import React from 'react';
import { ShieldAlert, ChevronRight, TrendingUp } from 'lucide-react';

const PriorityQueue = ({ latestRiskList, onSelectSite }) => {
  if (!latestRiskList || latestRiskList.length === 0) return null;

  // Rank locations by current risk score descending
  const sortedQueue = [...latestRiskList].sort((a, b) => (b.current_risk_score || 0) - (a.current_risk_score || 0));

  return (
    <div className="panel-card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <h3 className="panel-title" style={{ margin: 0 }}>
          <ShieldAlert size={16} color="var(--risk-high)" />
          HIGH-RISK PRIORITY QUEUE
        </h3>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          Ranked by Current Risk Index [0-100]
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '360px', overflowY: 'auto' }}>
        {sortedQueue.map((item, idx) => {
          const score = item.current_risk_score !== null && item.current_risk_score !== undefined ? Math.round(item.current_risk_score) : 'N/A';
          const level = item.current_risk_level || 'INSUFFICIENT_DATA';
          const badgeClass =
            level === 'HIGH' ? 'badge-high' :
            level === 'MODERATE' ? 'badge-moderate' :
            level === 'LOW' ? 'badge-low' : 'badge-nodata';

          return (
            <div
              key={item.site_id || idx}
              onClick={() => onSelectSite(item.site_id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.65rem 0.85rem',
                backgroundColor: 'var(--bg-dark)',
                border: '1px solid var(--bg-border)',
                borderRadius: '6px',
                cursor: 'pointer',
                transition: 'border-color 0.2s ease, background 0.2s ease',
              }}
              onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--accent-cyan)'}
              onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--bg-border)'}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{
                  fontSize: '0.75rem',
                  fontWeight: '800',
                  color: idx < 3 ? 'var(--accent-cyan)' : 'var(--text-muted)',
                  width: '24px',
                }}>
                  #{idx + 1}
                </span>

                <div>
                  <strong style={{ fontSize: '0.85rem', color: '#ffffff', display: 'block' }}>
                    {item.site_name}
                  </strong>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-sub)' }}>
                    {item.district}, {item.state} · Obs: {item.observation_date}
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '1.05rem', fontWeight: '800', color: '#ffffff' }}>
                    {score}
                  </div>
                  <span className={`badge ${badgeClass}`} style={{ fontSize: '0.65rem' }}>
                    {level}
                  </span>
                </div>
                <ChevronRight size={16} color="var(--text-muted)" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PriorityQueue;
