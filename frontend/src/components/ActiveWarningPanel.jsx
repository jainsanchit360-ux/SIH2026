import React from 'react';
import { ShieldAlert, CheckCircle, Eye, Truck, Check, Info } from 'lucide-react';

const ActiveWarningPanel = ({ activeAlerts, onAcknowledge, onUpdateStatus, onOpenDetail }) => {
  if (!activeAlerts || activeAlerts.length === 0) {
    return (
      <div className="panel-card" style={{ padding: '2rem', textAlign: 'center' }}>
        <CheckCircle size={28} color="#10b981" style={{ marginBottom: '0.5rem' }} />
        <h3 className="panel-title" style={{ justifyContent: 'center' }}>NO ACTIVE WARNINGS</h3>
        <p style={{ color: 'var(--text-sub)', fontSize: '0.8rem' }}>
          All monitored locations are operating within baseline parameters or have been resolved.
        </p>
      </div>
    );
  }

  return (
    <div className="panel-card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.85rem' }}>
        <h3 className="panel-title" style={{ margin: 0 }}>
          <ShieldAlert size={16} color="var(--risk-high)" />
          ACTIVE OPERATIONAL WARNINGS ({activeAlerts.length})
        </h3>
        <span className="badge badge-high" style={{ fontSize: '0.7rem' }}>
          REQUIRES AUTHORITY ACTION
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {activeAlerts.map((alert) => {
          const isSimulated = alert.simulation_mode || alert.data_source === 'SIMULATED_DEMO';
          const score = Math.round(alert.risk_score);
          const badgeClass = alert.severity === 'HIGH' ? 'badge-high' : 'badge-moderate';

          return (
            <div
              key={alert.alert_id}
              style={{
                backgroundColor: 'var(--bg-dark)',
                border: `1px solid ${isSimulated ? 'var(--accent-cyan)' : alert.severity === 'HIGH' ? 'var(--risk-high-border)' : 'var(--risk-mod-border)'}`,
                borderRadius: '8px',
                padding: '0.85rem',
                position: 'relative',
              }}
            >
              {/* Header bar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span className={`badge ${badgeClass}`}>
                    {alert.severity} WARNING
                  </span>
                  {isSimulated ? (
                    <span className="badge badge-moderate" style={{ fontSize: '0.65rem' }}>
                      SIMULATED DEMO ALERT
                    </span>
                  ) : (
                    <span className="badge badge-nodata" style={{ fontSize: '0.65rem' }}>
                      HISTORICAL PROTOTYPE ALERT
                    </span>
                  )}
                </div>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                  ID: {alert.alert_id}
                </span>
              </div>

              {/* Title & Info */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                <div>
                  <h4
                    onClick={() => onOpenDetail(alert)}
                    style={{ fontSize: '0.95rem', fontWeight: '800', color: '#ffffff', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
                  >
                    {alert.site_name}
                  </h4>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-sub)' }}>
                    {alert.district}, {alert.state} · Obs Date: <strong>{alert.observation_date}</strong>
                  </p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: '900', color: alert.severity === 'HIGH' ? 'var(--risk-high)' : 'var(--risk-mod)' }}>
                    {score} <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>/ 100</span>
                  </div>
                </div>
              </div>

              {/* Reason */}
              <p style={{ fontSize: '0.76rem', color: 'var(--text-main)', backgroundColor: 'var(--bg-panel)', padding: '0.4rem 0.65rem', borderRadius: '4px', border: '1px solid var(--bg-border)', marginBottom: '0.75rem' }}>
                <strong>Reason:</strong> {alert.reason}
              </p>

              {/* Workflow Status Bar & Actions */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--bg-border)', paddingTop: '0.6rem' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-sub)' }}>
                  Status: <strong style={{ color: '#ffffff', textTransform: 'uppercase' }}>{alert.status}</strong>
                </div>

                <div style={{ display: 'flex', gap: '0.4rem' }}>
                  {/* Status-specific action buttons */}
                  {alert.status === 'NEW' && (
                    <button
                      onClick={() => onAcknowledge(alert.alert_id)}
                      className="btn-primary"
                      style={{ fontSize: '0.72rem', padding: '0.3rem 0.65rem', backgroundColor: 'var(--risk-mod)', display: 'flex', alignItems: 'center', gap: '0.2rem' }}
                    >
                      <Check size={12} /> Acknowledge
                    </button>
                  )}

                  {alert.status === 'ACKNOWLEDGED' && (
                    <>
                      <button
                        onClick={() => onUpdateStatus(alert.alert_id, 'MONITORING')}
                        className="btn-secondary"
                        style={{ fontSize: '0.72rem', padding: '0.3rem 0.65rem', display: 'flex', alignItems: 'center', gap: '0.2rem' }}
                      >
                        <Eye size={12} /> Start Monitoring
                      </button>
                      <button
                        onClick={() => onUpdateStatus(alert.alert_id, 'RESPONSE_DISPATCHED')}
                        className="btn-primary"
                        style={{ fontSize: '0.72rem', padding: '0.3rem 0.65rem', backgroundColor: 'var(--accent-blue)', display: 'flex', alignItems: 'center', gap: '0.2rem' }}
                      >
                        <Truck size={12} /> Dispatch Response
                      </button>
                    </>
                  )}

                  {alert.status === 'MONITORING' && (
                    <>
                      <button
                        onClick={() => onUpdateStatus(alert.alert_id, 'RESPONSE_DISPATCHED')}
                        className="btn-primary"
                        style={{ fontSize: '0.72rem', padding: '0.3rem 0.65rem', backgroundColor: 'var(--accent-blue)', display: 'flex', alignItems: 'center', gap: '0.2rem' }}
                      >
                        <Truck size={12} /> Dispatch Response
                      </button>
                      <button
                        onClick={() => onUpdateStatus(alert.alert_id, 'RESOLVED')}
                        className="btn-secondary"
                        style={{ fontSize: '0.72rem', padding: '0.3rem 0.65rem', color: 'var(--risk-low)', borderColor: 'var(--risk-low-border)', display: 'flex', alignItems: 'center', gap: '0.2rem' }}
                      >
                        <CheckCircle size={12} /> Resolve
                      </button>
                    </>
                  )}

                  {alert.status === 'RESPONSE_DISPATCHED' && (
                    <button
                      onClick={() => onUpdateStatus(alert.alert_id, 'RESOLVED')}
                      className="btn-primary"
                      style={{ fontSize: '0.72rem', padding: '0.3rem 0.65rem', backgroundColor: 'var(--risk-low)', display: 'flex', alignItems: 'center', gap: '0.2rem' }}
                    >
                      <CheckCircle size={12} /> Mark Resolved
                    </button>
                  )}

                  <button
                    onClick={() => onOpenDetail(alert)}
                    className="btn-secondary"
                    style={{ fontSize: '0.72rem', padding: '0.3rem 0.6rem' }}
                  >
                    Details & Notes
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ActiveWarningPanel;
