import React, { useState } from 'react';
import { Search, MapPin, Filter } from 'lucide-react';

const LocationSearch = ({ locations, selectedSiteId, onSelectLocation }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedState, setSelectedState] = useState('ALL');

  // Extract unique states list
  const states = ['ALL', ...Array.from(new Set(locations.map((loc) => loc.state))).sort()];

  // Filter locations
  const filteredLocations = locations.filter((loc) => {
    const matchesState = selectedState === 'ALL' || loc.state === selectedState;
    const matchesSearch =
      loc.site_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      loc.district.toLowerCase().includes(searchTerm.toLowerCase()) ||
      loc.state.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesState && matchesSearch;
  });

  return (
    <div style={{
      padding: '1rem',
      backgroundColor: 'var(--bg-panel)',
      borderBottom: '1px solid var(--bg-border)',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.75rem',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <MapPin size={16} color="var(--accent-cyan)" />
        <span style={{ fontSize: '0.85rem', fontWeight: '700', color: '#ffffff' }}>
          MONITORED PILOT LOCATIONS ({locations.length})
        </span>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem' }}>
        {/* Search input */}
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          backgroundColor: 'var(--bg-dark)',
          border: '1px solid var(--bg-border)',
          borderRadius: '6px',
          padding: '0.4rem 0.65rem',
        }}>
          <Search size={14} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search site, district..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#ffffff',
              fontSize: '0.8rem',
              width: '100%',
            }}
          />
        </div>

        {/* State Filter dropdown */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.35rem',
          backgroundColor: 'var(--bg-dark)',
          border: '1px solid var(--bg-border)',
          borderRadius: '6px',
          padding: '0.4rem 0.5rem',
        }}>
          <Filter size={13} color="var(--text-muted)" />
          <select
            value={selectedState}
            onChange={(e) => setSelectedState(e.target.value)}
            style={{
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#ffffff',
              fontSize: '0.78rem',
              cursor: 'pointer',
            }}
          >
            {states.map((st) => (
              <option key={st} value={st} style={{ backgroundColor: 'var(--bg-panel)', color: '#ffffff' }}>
                {st === 'ALL' ? 'All States' : st}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Direct Site Select dropdown */}
      <select
        value={selectedSiteId || ''}
        onChange={(e) => onSelectLocation(e.target.value)}
        style={{
          width: '100%',
          padding: '0.5rem',
          backgroundColor: 'var(--bg-dark)',
          border: '1px solid var(--bg-border)',
          borderRadius: '6px',
          color: '#ffffff',
          fontSize: '0.8rem',
          outline: 'none',
          cursor: 'pointer',
        }}
      >
        <option value="" disabled>
          Select a location from list ({filteredLocations.length} match)...
        </option>
        {filteredLocations.map((loc) => (
          <option key={loc.site_id} value={loc.site_id} style={{ backgroundColor: 'var(--bg-panel)', color: '#ffffff' }}>
            {loc.site_name} ({loc.district}, {loc.state})
          </option>
        ))}
      </select>
    </div>
  );
};

export default LocationSearch;
