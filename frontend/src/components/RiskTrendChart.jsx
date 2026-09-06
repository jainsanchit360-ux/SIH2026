import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { TrendingUp, Calendar } from 'lucide-react';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const RiskTrendChart = ({ timeseries, loading, siteName }) => {
  if (loading) {
    return (
      <div className="panel-card" style={{ height: '320px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--text-sub)', fontSize: '0.85rem' }}>Loading historical risk timeseries...</p>
      </div>
    );
  }

  if (!timeseries || timeseries.length === 0) {
    return (
      <div className="panel-card" style={{ height: '320px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
        <TrendingUp size={28} color="var(--text-muted)" style={{ marginBottom: '0.5rem' }} />
        <h3 className="panel-title">RISK SCORE TIMESERIES TREND</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
          Select a monitored location to view its historical risk trajectory across observations.
        </p>
      </div>
    );
  }

  // Filter or format valid chronological data points
  const labels = timeseries.map((rec) => rec.observation_date);
  const riskScores = timeseries.map((rec) => rec.current_risk_score !== null && rec.current_risk_score !== undefined ? rec.current_risk_score : null);
  const triggerScores = timeseries.map((rec) => rec.dynamic_trigger_score !== null && rec.dynamic_trigger_score !== undefined ? rec.dynamic_trigger_score : null);

  const data = {
    labels,
    datasets: [
      {
        label: 'Current Risk Score [0-100]',
        data: riskScores,
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239, 68, 68, 0.12)',
        borderWidth: 2.5,
        tension: 0.3,
        pointRadius: 3,
        pointHoverRadius: 6,
        fill: true,
        spanGaps: false, // Preserve gaps honestly across missing observations
      },
      {
        label: 'Dynamic Trigger Score [0-100]',
        data: triggerScores,
        borderColor: '#38bdf8',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        borderDash: [4, 4],
        tension: 0.3,
        pointRadius: 2,
        spanGaps: false,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: '#94a3b8',
          font: { size: 11, weight: '600' },
          boxWidth: 12,
        },
      },
      tooltip: {
        backgroundColor: '#111827',
        borderColor: '#1e293b',
        borderWidth: 1,
        titleColor: '#ffffff',
        bodyColor: '#cbd5e1',
        padding: 10,
        callbacks: {
          label: (context) => {
            const val = context.parsed.y;
            return `${context.dataset.label}: ${val !== null ? val.toFixed(1) : 'N/A'}`;
          },
        },
      },
    },
    scales: {
      x: {
        grid: { color: 'rgba(30, 41, 59, 0.5)' },
        ticks: { color: '#64748b', font: { size: 10 }, maxRotation: 45 },
      },
      y: {
        min: 0,
        max: 100,
        grid: { color: 'rgba(30, 41, 59, 0.5)' },
        ticks: { color: '#64748b', font: { size: 10 } },
      },
    },
  };

  return (
    <div className="panel-card" style={{ height: '340px', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <h3 className="panel-title" style={{ margin: 0 }}>
          <TrendingUp size={16} color="var(--accent-cyan)" />
          RISK TIMESERIES TREND ({siteName || 'SELECTED LOCATION'})
        </h3>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <Calendar size={12} /> {timeseries.length} Observations
        </span>
      </div>

      <div style={{ flex: 1, position: 'relative', width: '100%', minHeight: 0 }}>
        <Line data={data} options={options} />
      </div>
    </div>
  );
};

export default RiskTrendChart;
