import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Health check endpoint
 */
export const getHealth = async () => {
  try {
    const res = await apiClient.get('/health');
    return res.data;
  } catch (error) {
    console.error('API Error (getHealth):', error);
    throw error;
  }
};

/**
 * System status & freshness metadata
 */
export const getSystemStatus = async () => {
  try {
    const res = await apiClient.get('/api/v1/system/status');
    return res.data;
  } catch (error) {
    console.error('API Error (getSystemStatus):', error);
    throw error;
  }
};

/**
 * Monitored locations list
 */
export const getLocations = async () => {
  try {
    const res = await apiClient.get('/api/v1/locations');
    return res.data;
  } catch (error) {
    console.error('API Error (getLocations):', error);
    throw error;
  }
};

/**
 * Latest risk records across all locations
 */
export const getLatestRisk = async () => {
  try {
    const res = await apiClient.get('/api/v1/risk/latest');
    return res.data;
  } catch (error) {
    console.error('API Error (getLatestRisk):', error);
    throw error;
  }
};

/**
 * Latest risk record for a specific site_id
 */
export const getRiskBySite = async (siteId) => {
  try {
    const res = await apiClient.get(`/api/v1/risk/${encodeURIComponent(siteId)}`);
    return res.data;
  } catch (error) {
    console.error(`API Error (getRiskBySite ${siteId}):`, error);
    throw error;
  }
};

/**
 * Risk timeseries for a specific site_id
 */
export const getRiskTimeseries = async (siteId, startDate, endDate) => {
  try {
    const params = {};
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    const res = await apiClient.get(`/api/v1/risk/${encodeURIComponent(siteId)}/timeseries`, { params });
    return res.data;
  } catch (error) {
    console.error(`API Error (getRiskTimeseries ${siteId}):`, error);
    throw error;
  }
};

/**
 * Layer 2 dynamic environmental factors for a site_id
 */
export const getEnvironmentBySite = async (siteId) => {
  try {
    const res = await apiClient.get(`/api/v1/environment/${encodeURIComponent(siteId)}`);
    return res.data;
  } catch (error) {
    console.error(`API Error (getEnvironmentBySite ${siteId}):`, error);
    throw error;
  }
};

/**
 * Layer 1 static susceptibility metrics for a site_id
 */
export const getSusceptibilityBySite = async (siteId) => {
  try {
    const res = await apiClient.get(`/api/v1/susceptibility/${encodeURIComponent(siteId)}`);
    return res.data;
  } catch (error) {
    console.error(`API Error (getSusceptibilityBySite ${siteId}):`, error);
    throw error;
  }
};

/**
 * Explainability narrative breakdown for a site_id
 */
export const getExplanationBySite = async (siteId) => {
  try {
    const res = await apiClient.get(`/api/v1/explanation/${encodeURIComponent(siteId)}`);
    return res.data;
  } catch (error) {
    console.error(`API Error (getExplanationBySite ${siteId}):`, error);
    throw error;
  }
};

/**
 * GeoJSON FeatureCollection for Leaflet GIS map
 */
export const getMapRiskGeoJSON = async () => {
  try {
    const res = await apiClient.get('/api/v1/map/risk');
    return res.data;
  } catch (error) {
    console.error('API Error (getMapRiskGeoJSON):', error);
    throw error;
  }
};

/**
 * Demo what-if risk simulation
 */
export const simulateDemoScenario = async (payload) => {
  try {
    const res = await apiClient.post('/api/v1/demo/simulate', payload);
    return res.data;
  } catch (error) {
    console.error('API Error (simulateDemoScenario):', error);
    throw error;
  }
};

// =====================================================================
// PHASE 10: ALERT & AUTHORITY COMMAND CENTER API CALLS
// =====================================================================

export const getAlerts = async (params = {}) => {
  try {
    const res = await apiClient.get('/api/v1/alerts', { params });
    return res.data;
  } catch (error) {
    console.error('API Error (getAlerts):', error);
    throw error;
  }
};

export const getAlertSummary = async () => {
  try {
    const res = await apiClient.get('/api/v1/alerts/summary');
    return res.data;
  } catch (error) {
    console.error('API Error (getAlertSummary):', error);
    throw error;
  }
};

export const getActiveAlerts = async () => {
  try {
    const res = await apiClient.get('/api/v1/alerts/active');
    return res.data;
  } catch (error) {
    console.error('API Error (getActiveAlerts):', error);
    throw error;
  }
};

export const getAlertHistory = async () => {
  try {
    const res = await apiClient.get('/api/v1/alerts/history');
    return res.data;
  } catch (error) {
    console.error('API Error (getAlertHistory):', error);
    throw error;
  }
};

export const getAlertById = async (alertId) => {
  try {
    const res = await apiClient.get(`/api/v1/alerts/${encodeURIComponent(alertId)}`);
    return res.data;
  } catch (error) {
    console.error(`API Error (getAlertById ${alertId}):`, error);
    throw error;
  }
};

export const acknowledgeAlert = async (alertId, acknowledgedBy = 'District Control Room') => {
  try {
    const res = await apiClient.post(`/api/v1/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
      acknowledged_by: acknowledgedBy,
    });
    return res.data;
  } catch (error) {
    console.error(`API Error (acknowledgeAlert ${alertId}):`, error);
    throw error;
  }
};

export const updateAlertStatus = async (alertId, newStatus, performedBy = 'Authority Officer', reasonOrNote = null) => {
  try {
    const res = await apiClient.patch(`/api/v1/alerts/${encodeURIComponent(alertId)}/status`, {
      new_status: newStatus,
      performed_by: performedBy,
      reason_or_note: reasonOrNote,
    });
    return res.data;
  } catch (error) {
    console.error(`API Error (updateAlertStatus ${alertId}):`, error);
    throw error;
  }
};

export const addAlertNote = async (alertId, noteText, author = 'Authority Officer') => {
  try {
    const res = await apiClient.post(`/api/v1/alerts/${encodeURIComponent(alertId)}/notes`, {
      note: noteText,
      author: author,
    });
    return res.data;
  } catch (error) {
    console.error(`API Error (addAlertNote ${alertId}):`, error);
    throw error;
  }
};

export const simulateAndAlert = async (payload) => {
  try {
    const res = await apiClient.post('/api/v1/demo/simulate-and-alert', payload);
    return res.data;
  } catch (error) {
    console.error('API Error (simulateAndAlert):', error);
    throw error;
  }
};

export const resetDemoAlerts = async () => {
  try {
    const res = await apiClient.post('/api/v1/demo/reset');
    return res.data;
  } catch (error) {
    console.error('API Error (resetDemoAlerts):', error);
    throw error;
  }
};

export default {
  getHealth,
  getSystemStatus,
  getLocations,
  getLatestRisk,
  getRiskBySite,
  getRiskTimeseries,
  getEnvironmentBySite,
  getSusceptibilityBySite,
  getExplanationBySite,
  getMapRiskGeoJSON,
  simulateDemoScenario,
  getAlerts,
  getAlertSummary,
  getActiveAlerts,
  getAlertHistory,
  getAlertById,
  acknowledgeAlert,
  updateAlertStatus,
  addAlertNote,
  simulateAndAlert,
  resetDemoAlerts,
};
