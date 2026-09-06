import React, { useState } from 'react';
import { X, ShieldAlert, Calendar, MapPin, Layers, Zap, MessageSquare, History, Send, AlertTriangle } from 'lucide-react';

const AlertDetailModal = ({ alert, onClose, onAddNote, onUpdateStatus }) => {
  const [noteText, setNoteText] = useState('');
  const [authorName, setAuthorName] = useState('District Control Room Operator');
  const [submittingNote, setSubmittingNote] = useState(false);

  if (!alert) return null;

  const isSimulated = alert.simulation_mode || alert.data_source === 'SIMULATED_DEMO';
  const score = Math.round(alert.risk_score);
  const badgeClass = alert.severity === 'HIGH' ? 'badge-high' : 'badge-moderate';

  const handleNoteSubmit = async (e) => {
    e.preventDefault();
    if (!noteText.trim()) return;
    setSubmittingNote(true);
    try {
      await onAddNote(alert.alert_id, noteText.trim(), authorName.trim() || 'Operator');
      setNoteText('');
    } catch (err) {
      console.error('Error adding note:', err);
    } finally {
      setSubmittingNote(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(4px)',
      zIndex: 1000,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1.5rem',
    }}>
      <div style={{
        backgroundColor: 'var(--bg-panel)',
        border: '1px solid var(--bg-border)',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '800px',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 20px 50px rgba(0, 0, 0, 0.8)',
        overflow: 'hidden',
      }}>
        {/* Modal Header */}
        <div style={{
          padding: '1.25rem 1.5rem',
          borderBottom: '1px solid var(--bg-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: 'var(--bg-panel-header)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              backgroundColor: alert.severity === 'HIGH' ? 'var(--risk-high-bg)' : 'var(--risk-mod-bg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <ShieldAlert size={20} color={alert.severity === 'HIGH' ? 'var(--risk-high)' : 'var(--risk-mod)'} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: '800', color: '#ffffff' }}>
                  {alert.site_name}
                </h3>
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
              <p style={{ fontSize: '0.75rem', color: 'var(--text-sub)' }}>
                Alert ID: {alert.alert_id} · State: {alert.state} · District: {alert.district}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-sub)',
              cursor: 'pointer',
              padding: '0.4rem',
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Body Scrollable */}
        <div style={{ padding: '1.5rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Scientific Disclaimer Warning */}
          <div style={{
            padding: '0.65rem 0.85rem',
            backgroundColor: 'rgba(245, 158, 11, 0.12)',
            border: '1px solid rgba(245, 158, 11, 0.3)',
            borderRadius: '6px',
            fontSize: '0.75rem',
            color: 'var(--risk-mod)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}>
            <AlertTriangle size={15} />
            <span><strong>{alert.calibration_disclaimer}</strong></span>
          </div>

          {/* Key Metrics Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', fontSize: '0.78rem' }}>
            <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--bg-border)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Fused Risk Index:</span>
              <div style={{ fontSize: '1.4rem', fontWeight: '900', color: '#ffffff' }}>
                {score} <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>/ 100</span>
              </div>
            </div>

            <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--bg-border)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Static Susceptibility:</span>
              <div style={{ fontSize: '1.2rem', fontWeight: '800', color: 'var(--accent-blue)' }}>
                {alert.static_susceptibility_score !== null ? Math.round(alert.static_susceptibility_score) : 'N/A'}
              </div>
            </div>

            <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--bg-border)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Dynamic Trigger:</span>
              <div style={{ fontSize: '1.2rem', fontWeight: '800', color: 'var(--accent-cyan)' }}>
                {alert.dynamic_trigger_score !== null ? Math.round(alert.dynamic_trigger_score) : 'N/A'}
              </div>
            </div>

            <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--bg-border)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Workflow Status:</span>
              <div style={{ fontSize: '1rem', fontWeight: '800', color: 'var(--accent-cyan)', textTransform: 'uppercase', marginTop: '0.2rem' }}>
                {alert.status}
              </div>
            </div>
          </div>

          {/* Environmental Trigger Breakdown */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.85rem', borderRadius: '6px', border: '1px solid var(--bg-border)', fontSize: '0.78rem' }}>
            <strong style={{ color: 'var(--text-sub)', display: 'block', marginBottom: '0.4rem', textTransform: 'uppercase' }}>
              Hydrometeorological Parameters
            </strong>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem' }}>
              <div>24h Rain: <strong style={{ color: '#ffffff' }}>{alert.rainfall_1d !== null ? `${alert.rainfall_1d.toFixed(1)} mm` : 'N/A'}</strong></div>
              <div>3-Day Rain: <strong style={{ color: '#ffffff' }}>{alert.rainfall_3d !== null ? `${alert.rainfall_3d.toFixed(1)} mm` : 'N/A'}</strong></div>
              <div>7-Day Rain: <strong style={{ color: '#ffffff' }}>{alert.rainfall_7d !== null ? `${alert.rainfall_7d.toFixed(1)} mm` : 'N/A'}</strong></div>
              <div>Soil Moisture: <strong style={{ color: '#ffffff' }}>{alert.soil_moisture !== null ? `${(alert.soil_moisture * 100).toFixed(1)}%` : 'N/A'}</strong></div>
            </div>
          </div>

          {/* Reason & Risk Factors */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.85rem', borderRadius: '6px', border: '1px solid var(--bg-border)', fontSize: '0.8rem' }}>
            <p style={{ marginBottom: '0.4rem' }}>
              <strong style={{ color: 'var(--accent-cyan)' }}>Operational Reason: </strong> {alert.reason}
            </p>
            {alert.major_risk_factors.length > 0 && (
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: '0.4rem' }}>
                {alert.major_risk_factors.map((f, i) => (
                  <span key={i} style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', backgroundColor: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)', borderRadius: '4px' }}>
                    {f}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Response Notes Log & Input */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.85rem', borderRadius: '6px', border: '1px solid var(--bg-border)' }}>
            <h4 style={{ fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-sub)', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.75rem' }}>
              <MessageSquare size={14} color="var(--accent-cyan)" />
              OPERATIONAL RESPONSE NOTES ({alert.response_notes?.length || 0})
            </h4>

            {/* Notes List */}
            {alert.response_notes && alert.response_notes.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.75rem', maxHeight: '150px', overflowY: 'auto' }}>
                {alert.response_notes.map((n, idx) => (
                  <div key={idx} style={{ backgroundColor: 'var(--bg-panel)', padding: '0.5rem 0.75rem', borderRadius: '4px', border: '1px solid var(--bg-border)', fontSize: '0.75rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                      <strong>{n.author}</strong>
                      <span>{n.timestamp}</span>
                    </div>
                    <p style={{ color: '#ffffff' }}>{n.note}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                No operational notes added yet for this alert.
              </p>
            )}

            {/* Note Form */}
            <form onSubmit={handleNoteSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <textarea
                placeholder="Enter operational note (e.g. District control room informed, SDRF team dispatched)..."
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                rows={2}
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  backgroundColor: 'var(--bg-panel)',
                  border: '1px solid var(--bg-border)',
                  borderRadius: '4px',
                  color: '#ffffff',
                  fontSize: '0.78rem',
                  outline: 'none',
                  resize: 'none',
                }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <input
                  type="text"
                  placeholder="Author Title"
                  value={authorName}
                  onChange={(e) => setAuthorName(e.target.value)}
                  style={{
                    padding: '0.3rem 0.5rem',
                    backgroundColor: 'var(--bg-panel)',
                    border: '1px solid var(--bg-border)',
                    borderRadius: '4px',
                    color: 'var(--text-sub)',
                    fontSize: '0.72rem',
                    width: '240px',
                  }}
                />
                <button type="submit" disabled={submittingNote || !noteText.trim()} className="btn-primary" style={{ fontSize: '0.75rem', padding: '0.35rem 0.85rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  <Send size={12} /> Add Note
                </button>
              </div>
            </form>
          </div>

          {/* Workflow State Audit History */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.85rem', borderRadius: '6px', border: '1px solid var(--bg-border)', fontSize: '0.75rem' }}>
            <h4 style={{ fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-sub)', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.5rem' }}>
              <History size={14} color="var(--text-sub)" />
              WORKFLOW STATE AUDIT LOG
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              {alert.audit_history.map((a, idx) => (
                <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-sub)', borderBottom: '1px solid var(--bg-border)', paddingBottom: '0.2rem' }}>
                  <span>Transitioned from <strong>{a.from_status}</strong> → <strong style={{ color: 'var(--accent-cyan)' }}>{a.to_status}</strong> by {a.performed_by}</span>
                  <span style={{ color: 'var(--text-muted)' }}>{a.timestamp}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AlertDetailModal;
