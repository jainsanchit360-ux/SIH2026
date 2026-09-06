/**
 * Frontend API Client & Utility Unit Tests
 */

import { getHealth, getSystemStatus, getLocations, getMapRiskGeoJSON } from './client.js';

describe('Frontend API Client Test Suite', () => {
  test('client module exposes required API functions', () => {
    expect(typeof getHealth).toBe('function');
    expect(typeof getSystemStatus).toBe('function');
    expect(typeof getLocations).toBe('function');
    expect(typeof getMapRiskGeoJSON).toBe('function');
  });
});
