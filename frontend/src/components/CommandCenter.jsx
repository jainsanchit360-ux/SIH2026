import React, { useState } from 'react';
import { ShieldAlert, RotateCcw, AlertOctagon } from 'lucide-react';
import AlertSummaryCards from './AlertSummaryCards';
import PriorityQueue from './PriorityQueue';
import ActiveWarningPanel from './ActiveWarningPanel';
import AlertHistoryTable from './AlertHistoryTable';
import { resetDemoAlerts } from '../api/client';

const CommandCenter = ({
  summary,
  activeAlerts,
  alertHistory,
  latestRiskList,
  onAcknowledge,
  onUpdateStatus,
  onOpenDetail,
  onSelectSite,
  onRefreshData,
}) => {
  const [resetting, setResetting] = useState(false);
  const [resetMsg, setResetMsg] = useState(null);

  const handleResetDemo = async () => {
    if (!window.confirm('Reset simulated demo operational alerts? Real scientific historical datasets will NOT be modified.')) {
      return;
    }
    setResetting(true);
    setResetMsg(null);
    try {
      const res = await resetDemoAlerts();
      setResetMsg(`Reset successful: Purged ${res.deleted_count} simulated demo alert records.`);
      if (onRefreshData) onRefreshData();
    } catch (err) {
      console.error('Error resetting demo alerts:', err);
      setResetMsg('Failed to reset demo alerts.');
    } finally {
      setResetting(false);
    }
  };

  return (
    <div style={{ padding: '1.5rem', backgroundColor: 'var(--bg-dark)', flex: 1, overflowY: 'auto' }}>
      {/* Top Banner */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <h2 style={{ fontSize: '1.4rem', fontWeight: '900', color: '#ffffff', letterSpacing: '-0.02em' }}>
              DISTRICT & STATE AUTHORITY COMMAND CENTER
            </h2>
            <span className="badge badge-high" style={{ fontSize: '0.7rem' }}>
              OPERATIONAL DECISION SUPPORT
            </span>
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-sub)' }}>
            Real-Time Prototype Warning Queue, Action Tracking & Emergency Dispatch Lifecycle
          </p>
        </div>

        <button
          onClick={handleResetDemo}
          disabled={resetting}
          className="btn-secondary"
          style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.4rem', borderColor: 'var(--accent-cyan)' }}
        >
          <RotateCcw size={14} color="var(--accent-cyan)" />
          {resetting ? 'Resetting...' : 'Reset Demo Alerts'}
        </button>
      </div>

      {resetMsg && (
        <div style={{
          backgroundColor: 'rgba(56, 189, 248, 0.12)',
          border: '1px solid var(--accent-cyan)',
          color: '#ffffff',
          padding: '0.5rem 1rem',
          borderRadius: '6px',
          fontSize: '0.78rem',
          marginBottom: '1rem',
        }}>
          {resetMsg}
        </div>
      )}

      {/* Summary Cards */}
      <AlertSummaryCards summary={summary} />

      {/* Grid Layout: Active Warnings + Priority Queue */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '1.25rem', marginBottom: '1.25rem' }}>
        <ActiveWarningPanel
          activeAlerts={activeAlerts}
          onAcknowledge={onAcknowledge}
          onUpdateStatus={onUpdateStatus}
          onOpenDetail={onOpenDetail}
        />
        <PriorityQueue
          latestRiskList={latestRiskList}
          onSelectSite={onSelectSite}
        />
      </div>

      {/* Complete Alert History Log */}
      <AlertHistoryTable
        alertHistory={alertHistory}
        onOpenDetail={onOpenDetail}
      />
    </div>
  );
};

export default CommandCenter;
