import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Layers, RotateCcw, MapPin } from 'lucide-react';

// Center of North-Eastern Region (NER) India: ~25.5° N, 92.5° E
const DEFAULT_CENTER = [25.5, 92.5];
const DEFAULT_ZOOM = 7;

// Create custom L.divIcon marker based on risk level, score, and active alert state
const createRiskIcon = (riskLevel, riskScore, isSelected, hasActiveAlert) => {
  const levelClass = (riskLevel || 'NODATA').toLowerCase();
  const scoreText = riskScore !== null && riskScore !== undefined && !isNaN(riskScore)
    ? Math.round(riskScore)
    : '--';

  const selectedClass = isSelected ? 'selected' : '';
  const alertClass = hasActiveAlert ? 'active-alert' : '';

  return L.divIcon({
    className: `custom-risk-marker ${levelClass} ${selectedClass} ${alertClass}`,
    html: `<span>${scoreText}</span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
};

// Component to dynamically re-center/fly to selected location
function MapRecenter({ selectedLocation }) {
  const map = useMap();
  useEffect(() => {
    if (selectedLocation && selectedLocation.latitude && selectedLocation.longitude) {
      map.flyTo([selectedLocation.latitude, selectedLocation.longitude], 10, {
        duration: 1.2,
      });
    }
  }, [selectedLocation, map]);
  return null;
}

const MapView = ({ geojson, selectedSiteId, onSelectLocation, locations, activeAlerts = [] }) => {
  // Extract features array safely from GeoJSON FeatureCollection
  const features = geojson?.features || [];

  // Create a set of site_ids that currently have active alerts
  const alertSiteIds = new Set(
    activeAlerts
      .filter((a) => a.status !== 'RESOLVED')
      .map((a) => a.site_id)
  );

  const handleResetView = (map) => {
    map.flyTo(DEFAULT_CENTER, DEFAULT_ZOOM, { duration: 1 });
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        zoomControl={false}
        scrollWheelZoom={true}
        style={{ width: '100%', height: '100%' }}
      >
        {/* CartoDB Dark Matter basemap tiles */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          maxZoom={19}
        />

        {/* Feature Markers */}
        {features.map((feature, idx) => {
          const props = feature.properties || {};
          const coords = feature.geometry?.coordinates || []; // [lon, lat]
          if (coords.length < 2) return null;

          const lon = coords[0];
          const lat = coords[1];
          const siteId = props.site_id;
          const isSelected = siteId === selectedSiteId;
          const hasActiveAlert = alertSiteIds.has(siteId);

          const riskLevel = props.current_risk_level || 'NODATA';
          const riskScore = props.current_risk_score;

          return (
            <Marker
              key={siteId || idx}
              position={[lat, lon]} // Leaflet requires [latitude, longitude]
              icon={createRiskIcon(riskLevel, riskScore, isSelected, hasActiveAlert)}
              eventHandlers={{
                click: () => onSelectLocation(siteId),
              }}
            >
              <Tooltip direction="top" offset={[0, -10]} opacity={0.95}>
                <div style={{ fontSize: '0.8rem', padding: '0.2rem' }}>
                  <strong style={{ color: '#ffffff' }}>{props.site_name}</strong>
                  <br />
                  <span style={{ color: 'var(--text-sub)' }}>{props.state} · {props.district}</span>
                  <br />
                  <span>Risk Score: <strong>{riskScore !== null ? Math.round(riskScore) : 'N/A'}</strong> ({riskLevel})</span>
                </div>
              </Tooltip>
            </Marker>
          );
        })}

        {/* Dynamic Fly-to controller */}
        <MapRecenter
          selectedLocation={
            selectedSiteId
              ? locations.find((loc) => loc.site_id === selectedSiteId)
              : null
          }
        />
      </MapContainer>

      {/* Map Overlay: Risk Level Legend */}
      <div style={{
        position: 'absolute',
        bottom: '24px',
        left: '24px',
        zIndex: 400,
        backgroundColor: 'rgba(17, 24, 39, 0.92)',
        backdropFilter: 'blur(8px)',
        border: '1px solid var(--bg-border)',
        borderRadius: '8px',
        padding: '0.75rem 1rem',
        fontSize: '0.78rem',
        boxShadow: '0 8px 20px rgba(0,0,0,0.5)',
      }}>
        <div style={{ fontWeight: '700', color: 'var(--text-sub)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Layers size={14} />
          <span>RISK LEVEL LEGEND</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: 'var(--risk-high)' }}></span>
            <span style={{ color: '#ffffff', fontWeight: '600' }}>HIGH RISK</span>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>(Score ≥ 70)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: 'var(--risk-mod)' }}></span>
            <span style={{ color: '#ffffff', fontWeight: '600' }}>MODERATE RISK</span>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>(Score 40–69)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: 'var(--risk-low)' }}></span>
            <span style={{ color: '#ffffff', fontWeight: '600' }}>LOW RISK</span>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>(Score &lt; 40)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: 'var(--risk-nodata)' }}></span>
            <span style={{ color: 'var(--text-sub)' }}>INSUFFICIENT DATA</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MapView;
