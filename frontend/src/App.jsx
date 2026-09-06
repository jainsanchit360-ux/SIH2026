import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import Footer from './components/Footer';
import MapView from './components/MapView';
import LocationSearch from './components/LocationSearch';
import LocationPanel from './components/LocationPanel';
import ExplainabilityPanel from './components/ExplainabilityPanel';
import RiskTrendChart from './components/RiskTrendChart';
import RiskLayerComparison from './components/RiskLayerComparison';
import DemoSimulationPanel from './components/DemoSimulationPanel';
import SystemStatus from './components/SystemStatus';
import CommandCenter from './components/CommandCenter';
import AlertDetailModal from './components/AlertDetailModal';

import {
  getHealth,
  getSystemStatus,
  getLocations,
  getMapRiskGeoJSON,
  getRiskBySite,
  getRiskTimeseries,
  getExplanationBySite,
  getAlertSummary,
  getActiveAlerts,
  getAlertHistory,
  acknowledgeAlert,
  updateAlertStatus,
  addAlertNote,
  resetDemoAlerts,
} from './api/client';

function App() {
  // Navigation & View Tab State ('MAP' | 'COMMAND_CENTER')
  const [activeTab, setActiveTab] = useState('MAP');

  // System & Core Data State
  const [systemStatus, setSystemStatus] = useState(null);
  const [isBackendConnected, setIsBackendConnected] = useState(false);
  const [locations, setLocations] = useState([]);
  const [geoJson, setGeoJson] = useState(null);

  // Selected Location Intelligence State
  const [selectedSiteId, setSelectedSiteId] = useState('GSI_SITE_01');
  const [selectedRiskRecord, setSelectedRiskRecord] = useState(null);
  const [selectedTimeseries, setSelectedTimeseries] = useState([]);
  const [selectedExplanation, setSelectedExplanation] = useState(null);

  // Phase 10 Alert & Operational Workflow State
  const [alertSummary, setAlertSummary] = useState(null);
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [alertHistory, setAlertHistory] = useState([]);
  const [selectedAlert, setSelectedAlert] = useState(null);

  const [loadingInitial, setLoadingInitial] = useState(true);
  const [loadingSiteData, setLoadingSiteData] = useState(false);
  const [backendError, setBackendError] = useState(null);

  // Fetch operational alert state (Summary, Active Warnings, History)
  const fetchAlertData = async () => {
    try {
      const [sumRes, actRes, histRes] = await Promise.all([
        getAlertSummary().catch(() => null),
        getActiveAlerts().catch(() => []),
        getAlertHistory().catch(() => []),
      ]);
      setAlertSummary(sumRes);
      setActiveAlerts(actRes || []);
      setAlertHistory(histRes || []);
    } catch (err) {
      console.error('Error fetching operational alert data:', err);
    }
  };

  // Initial Data Load (System status, locations, map GeoJSON, alerts)
  useEffect(() => {
    async function initDashboard() {
      try {
        setLoadingInitial(true);
        setBackendError(null);

        // Health check
        try {
          await getHealth();
          setIsBackendConnected(true);
        } catch {
          setIsBackendConnected(false);
        }

        // Fetch parallel system metadata, locations, GeoJSON map layer, and alerts
        const [statusRes, locsRes, geoJsonRes] = await Promise.all([
          getSystemStatus(),
          getLocations(),
          getMapRiskGeoJSON(),
        ]);

        setSystemStatus(statusRes);
        setLocations(locsRes || []);
        setGeoJson(geoJsonRes);

        // Fetch alert system data
        await fetchAlertData();

        // Default to first site if available
        if (locsRes && locsRes.length > 0) {
          const firstSiteId = locsRes[0].site_id;
          setSelectedSiteId(firstSiteId);
        }
      } catch (err) {
        console.error('Error initializing ResQtech dashboard:', err);
        setBackendError('Unable to connect to ResQtech FastAPI backend at http://127.0.0.1:8000. Ensure Uvicorn server is running.');
      } finally {
        setLoadingInitial(false);
      }
    }

    initDashboard();
  }, []);

  // Fetch site-specific intelligence whenever selectedSiteId changes
  useEffect(() => {
    if (!selectedSiteId) return;

    async function loadSiteIntelligence() {
      try {
        setLoadingSiteData(true);

        const [riskRes, tsRes, expRes] = await Promise.all([
          getRiskBySite(selectedSiteId).catch(() => null),
          getRiskTimeseries(selectedSiteId).catch(() => []),
          getExplanationBySite(selectedSiteId).catch(() => null),
        ]);

        setSelectedRiskRecord(riskRes);
        setSelectedTimeseries(tsRes || []);
        setSelectedExplanation(expRes);
      } catch (err) {
        console.error(`Error loading site intelligence for ${selectedSiteId}:`, err);
      } finally {
        setLoadingSiteData(false);
      }
    }

    loadSiteIntelligence();
  }, [selectedSiteId]);

  const handleSelectLocation = (siteId) => {
    if (siteId) {
      setSelectedSiteId(siteId);
    }
  };

  const handleSelectSiteFromAlert = (siteId) => {
    if (siteId) {
      setSelectedSiteId(siteId);
      setActiveTab('MAP');
    }
  };

  // Operational Workflow Actions
  const handleAcknowledgeAlert = async (alertId) => {
    try {
      const updated = await acknowledgeAlert(alertId, 'District Control Room');
      if (selectedAlert && selectedAlert.alert_id === alertId) {
        setSelectedAlert(updated);
      }
      await fetchAlertData();
    } catch (err) {
      console.error('Error acknowledging alert:', err);
    }
  };

  const handleUpdateStatusAlert = async (alertId, newStatus, reasonOrNote) => {
    try {
      const updated = await updateAlertStatus(alertId, newStatus, 'Authority Officer', reasonOrNote);
      if (selectedAlert && selectedAlert.alert_id === alertId) {
        setSelectedAlert(updated);
      }
      await fetchAlertData();
    } catch (err) {
      console.error('Error updating alert status:', err);
    }
  };

  const handleAddNoteAlert = async (alertId, noteText) => {
    try {
      const updated = await addAlertNote(alertId, noteText, 'Authority Officer');
      if (selectedAlert && selectedAlert.alert_id === alertId) {
        setSelectedAlert(updated);
      }
      await fetchAlertData();
    } catch (err) {
      console.error('Error adding alert note:', err);
    }
  };

  const handleResetDemo = async () => {
    try {
      await resetDemoAlerts();
      await fetchAlertData();
      if (selectedAlert?.simulation_mode) {
        setSelectedAlert(null);
      }
    } catch (err) {
      console.error('Error resetting demo alerts:', err);
    }
  };

  return (
    <div className="app-container">
      <Header
        systemStatus={systemStatus}
        isBackendConnected={isBackendConnected}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        unacknowledgedCount={alertSummary?.unacknowledged || 0}
      />

      {/* Backend Connection Error Banner */}
      {backendError && (
        <div style={{
          backgroundColor: 'rgba(239, 68, 68, 0.2)',
          borderBottom: '1px solid var(--risk-high)',
          color: '#ffffff',
          padding: '0.75rem 1.5rem',
          fontSize: '0.85rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <span><strong>Backend Offline:</strong> {backendError}</span>
          <button
            onClick={() => window.location.reload()}
            className="btn-primary"
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.65rem' }}
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* Main Display: Tab Switch between GIS Map Monitoring and Authority Command Center */}
      {activeTab === 'MAP' ? (
        <>
          {/* Main Split Screen: Left GIS Map, Right Intelligence Sidebar */}
          <main className="main-content">
            <div className="map-section">
              {loadingInitial ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-sub)' }}>
                  Loading interactive GIS map layers...
                </div>
              ) : (
                <MapView
                  geojson={geoJson}
                  selectedSiteId={selectedSiteId}
                  onSelectLocation={handleSelectLocation}
                  locations={locations}
                  activeAlerts={activeAlerts}
                />
              )}
            </div>

            <aside className="sidebar-section">
              <LocationSearch
                locations={locations}
                selectedSiteId={selectedSiteId}
                onSelectLocation={handleSelectLocation}
              />
              <LocationPanel
                riskRecord={selectedRiskRecord}
                loading={loadingSiteData}
                error={null}
              />
            </aside>
          </main>

          {/* Secondary Dashboard Analytics Grid */}
          <section className="secondary-dashboard">
            <div className="dashboard-grid">
              <ExplainabilityPanel
                explanation={selectedExplanation}
                loading={loadingSiteData}
              />
              <RiskTrendChart
                timeseries={selectedTimeseries}
                loading={loadingSiteData}
                siteName={selectedRiskRecord?.site_name}
              />
              <RiskLayerComparison
                record={selectedRiskRecord}
              />
              <DemoSimulationPanel
                selectedSite={selectedRiskRecord}
                onSimulationComplete={fetchAlertData}
              />
            </div>

            <div style={{ marginTop: '1.25rem' }}>
              <SystemStatus systemStatus={systemStatus} />
            </div>
          </section>
        </>
      ) : (
        <CommandCenter
          summary={alertSummary}
          activeAlerts={activeAlerts}
          alertHistory={alertHistory}
          locations={locations}
          onSelectAlert={(alert) => setSelectedAlert(alert)}
          onAcknowledge={handleAcknowledgeAlert}
          onUpdateStatus={handleUpdateStatusAlert}
          onResetDemo={handleResetDemo}
          onSelectSite={handleSelectSiteFromAlert}
        />
      )}

      {/* Alert Detail Modal Drawer */}
      {selectedAlert && (
        <AlertDetailModal
          alert={selectedAlert}
          onClose={() => setSelectedAlert(null)}
          onAcknowledge={handleAcknowledgeAlert}
          onUpdateStatus={handleUpdateStatusAlert}
          onAddNote={handleAddNoteAlert}
        />
      )}

      <Footer systemStatus={systemStatus} />
    </div>
  );
}

export default App;
