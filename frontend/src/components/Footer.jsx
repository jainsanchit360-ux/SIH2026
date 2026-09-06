import React from 'react';
import { AlertTriangle, Info } from 'lucide-react';

const Footer = ({ systemStatus }) => {
  const disclaimer = systemStatus?.calibration_disclaimer || "PROTOTYPE OPERATIONAL PARAMETERS — REQUIRES REGIONAL CALIBRATION";
  const apiVersion = systemStatus?.api_version || "0.1.0-prototype";

  return (
    <footer style={{
      height: '48px',
      backgroundColor: 'var(--bg-panel)',
      borderTop: '1px solid var(--bg-border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 1.5rem',
      fontSize: '0.75rem',
      color: 'var(--text-sub)',
      zIndex: 100,
    }}>
      {/* Disclaimer */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#f59e0b' }}>
        <AlertTriangle size={14} />
        <span style={{ fontWeight: '600', letterSpacing: '0.02em' }}>{disclaimer}</span>
      </div>

      {/* Center Scientific Attribution */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)' }}>
        <Info size={13} />
        <span>Data Provenance: NASA IMERG Rainfall (3B-DAY) + NASA SMAP L3 Soil Moisture + GSI Landslide Inventory</span>
      </div>

      {/* Version Tag */}
      <div>
        <span>API v{apiVersion} | ResQtech Prototype</span>
      </div>
    </footer>
  );
};

export default Footer;
