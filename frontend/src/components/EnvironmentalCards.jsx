import React from 'react';
import { CloudRain, Droplets } from 'lucide-react';

const EnvironmentalCards = ({ record }) => {
  const formatVal = (val, unit) => {
    if (val === null || val === undefined || isNaN(val)) return 'N/A';
    return `${val.toFixed(1)} ${unit}`;
  };

  const r1d = formatVal(record?.rainfall_1d, 'mm/day');
  const r3d = formatVal(record?.rainfall_3d, 'mm');
  const r7d = formatVal(record?.rainfall_7d, 'mm');
  
  const smRaw = record?.soil_moisture;
  let smText = 'N/A';
  if (smRaw !== null && smRaw !== undefined && !isNaN(smRaw)) {
    smText = smRaw > 1.0 ? `${smRaw.toFixed(1)}%` : `${(smRaw * 100).toFixed(1)}%`;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <h4 style={{ fontSize: '0.78rem', fontWeight: '700', color: 'var(--text-sub)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <CloudRain size={14} color="var(--accent-cyan)" />
        ENVIRONMENTAL TRIGGER INDICATORS
      </h4>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem' }}>
        {/* 24h Rainfall */}
        <div style={{
          backgroundColor: 'var(--bg-dark)',
          border: '1px solid var(--bg-border)',
          borderRadius: '6px',
          padding: '0.65rem',
        }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>24h Rainfall (IMERG)</span>
          <div style={{ fontSize: '1.05rem', fontWeight: '800', color: '#ffffff', marginTop: '0.2rem' }}>
            {r1d}
          </div>
        </div>

        {/* 3-day Rainfall */}
        <div style={{
          backgroundColor: 'var(--bg-dark)',
          border: '1px solid var(--bg-border)',
          borderRadius: '6px',
          padding: '0.65rem',
        }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>3-Day Rainfall Accumulation</span>
          <div style={{ fontSize: '1.05rem', fontWeight: '800', color: '#ffffff', marginTop: '0.2rem' }}>
            {r3d}
          </div>
        </div>

        {/* 7-day Rainfall */}
        <div style={{
          backgroundColor: 'var(--bg-dark)',
          border: '1px solid var(--bg-border)',
          borderRadius: '6px',
          padding: '0.65rem',
        }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>7-Day Rainfall Accumulation</span>
          <div style={{ fontSize: '1.05rem', fontWeight: '800', color: '#ffffff', marginTop: '0.2rem' }}>
            {r7d}
          </div>
        </div>

        {/* Soil Moisture */}
        <div style={{
          backgroundColor: 'var(--bg-dark)',
          border: '1px solid var(--bg-border)',
          borderRadius: '6px',
          padding: '0.65rem',
        }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
            <Droplets size={12} color="var(--accent-blue)" />
            Soil Moisture (SMAP)
          </span>
          <div style={{ fontSize: '1.05rem', fontWeight: '800', color: '#ffffff', marginTop: '0.2rem' }}>
            {smText}
          </div>
        </div>
      </div>
    </div>
  );
};

export default EnvironmentalCards;
