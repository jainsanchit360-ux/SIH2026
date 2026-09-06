import React, { useState } from 'react';
import { History, Search, Filter } from 'lucide-react';

const AlertHistoryTable = ({ alertHistory, onOpenDetail }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [sourceFilter, setSourceFilter] = useState('ALL');

  if (!alertHistory || alertHistory.length === 0) return null;

  const filteredHistory = alertHistory.filter((item) => {
    const matchesStatus = statusFilter === 'ALL' || item.status === statusFilter;
    const matchesSource =
      sourceFilter === 'ALL' ||
      (sourceFilter === 'SIMULATED' && (item.simulation_mode || item.data_source === 'SIMULATED_DEMO')) ||
      (sourceFilter === 'HISTORICAL' && (!item.simulation_mode && item.data_source === 'OFFLINE_HISTORICAL_CACHE'));

    const matchesSearch =
      item.site_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.alert_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.state.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (item.district && item.district.toLowerCase().includes(searchTerm.toLowerCase()));

    return matchesStatus && matchesSource && matchesSearch;
  });

  return (
    <div className="panel-card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.85rem' }}>
        <h3 className="panel-title" style={{ margin: 0 }}>
          <History size={16} color="var(--accent-cyan)" />
          COMPLETE ALERT HISTORY LOG ({filteredHistory.length})
        </h3>
      </div>

      {/* Filter Controls */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.85rem' }}>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'var(--bg-dark)', border: '1px solid var(--bg-border)', borderRadius: '6px', padding: '0.35rem 0.65rem' }}>
          <Search size={14} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search alert history by ID, site, state..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ background: 'transparent', border: 'none', outline: 'none', color: '#ffffff', fontSize: '0.78rem', width: '100%' }}
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ backgroundColor: 'var(--bg-dark)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: '#ffffff', fontSize: '0.78rem', padding: '0.35rem 0.5rem' }}
        >
          <option value="ALL">All Statuses</option>
          <option value="NEW">NEW</option>
          <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
          <option value="MONITORING">MONITORING</option>
          <option value="RESPONSE_DISPATCHED">RESPONSE DISPATCHED</option>
          <option value="RESOLVED">RESOLVED</option>
        </select>

        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          style={{ backgroundColor: 'var(--bg-dark)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: '#ffffff', fontSize: '0.78rem', padding: '0.35rem 0.5rem' }}
        >
          <option value="ALL">All Data Sources</option>
          <option value="HISTORICAL">Historical Cache</option>
          <option value="SIMULATED">Simulated Demo</option>
        </select>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem', textAlign: 'left' }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--bg-dark)', borderBottom: '1px solid var(--bg-border)', color: 'var(--text-sub)' }}>
              <th style={{ padding: '0.55rem 0.75rem' }}>Alert ID</th>
              <th style={{ padding: '0.55rem 0.75rem' }}>Location</th>
              <th style={{ padding: '0.55rem 0.75rem' }}>Obs Date</th>
              <th style={{ padding: '0.55rem 0.75rem' }}>Risk Score</th>
              <th style={{ padding: '0.55rem 0.75rem' }}>Severity</th>
              <th style={{ padding: '0.55rem 0.75rem' }}>Source</th>
              <th style={{ padding: '0.55rem 0.75rem' }}>Workflow Status</th>
              <th style={{ padding: '0.55rem 0.75rem', textAlign: 'right' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredHistory.map((item) => {
              const isSim = item.simulation_mode || item.data_source === 'SIMULATED_DEMO';
              const badgeClass = item.severity === 'HIGH' ? 'badge-high' : 'badge-moderate';

              return (
                <tr key={item.alert_id} style={{ borderBottom: '1px solid var(--bg-border)' }}>
                  <td style={{ padding: '0.55rem 0.75rem', fontWeight: '600', color: 'var(--accent-cyan)' }}>
                    {item.alert_id}
                  </td>
                  <td style={{ padding: '0.55rem 0.75rem', color: '#ffffff' }}>
                    <strong>{item.site_name}</strong> ({item.state})
                  </td>
                  <td style={{ padding: '0.55rem 0.75rem', color: 'var(--text-sub)' }}>
                    {item.observation_date}
                  </td>
                  <td style={{ padding: '0.55rem 0.75rem', fontWeight: '800', color: '#ffffff' }}>
                    {Math.round(item.risk_score)}
                  </td>
                  <td style={{ padding: '0.55rem 0.75rem' }}>
                    <span className={`badge ${badgeClass}`} style={{ fontSize: '0.65rem' }}>
                      {item.severity}
                    </span>
                  </td>
                  <td style={{ padding: '0.55rem 0.75rem' }}>
                    {isSim ? (
                      <span className="badge badge-moderate" style={{ fontSize: '0.65rem' }}>
                        SIMULATED
                      </span>
                    ) : (
                      <span className="badge badge-nodata" style={{ fontSize: '0.65rem' }}>
                        HISTORICAL
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '0.55rem 0.75rem', textTransform: 'uppercase', fontWeight: '700', color: item.status === 'RESOLVED' ? 'var(--risk-low)' : '#ffffff' }}>
                    {item.status}
                  </td>
                  <td style={{ padding: '0.55rem 0.75rem', textAlign: 'right' }}>
                    <button
                      onClick={() => onOpenDetail(item)}
                      className="btn-secondary"
                      style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem' }}
                    >
                      View
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default AlertHistoryTable;
