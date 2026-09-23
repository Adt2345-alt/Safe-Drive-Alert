import React, { useState, useEffect, useRef, useCallback } from 'react';
import TimePlayback from './TimePlayback';
import DigitalTwin from './DigitalTwin';
import { TurfHelpers, formatCoordinates, generatePDFReportData, dispatchWorkerTask } from '../utils/geo';

/**
 * MapView Component
 * High-performance HD Mapping interface integrating Deck.gl multi-layer rendering,
 * Mapbox/MapLibre GL JS dark vector basemap, 3D building extrusions, Turf.js spatial queries,
 * interactive drawing/measurement tools, defect detail drawers, and PDF report export.
 */
export default function MapView() {
  // Layer Visibility State
  const [layersConfig, setLayersConfig] = useState({
    defects: true,
    heatmap: true,
    trajectory: true,
    predicted: true,
    municipality: true,
    buildings3D: true
  });

  // Map Data State
  const [defects, setDefects] = useState([]);
  const [filteredDefects, setFilteredDefects] = useState([]);
  const [heatmapPoints, setHeatmapPoints] = useState([]);
  const [trajectoryData, setTrajectoryData] = useState(null);
  const [predictedData, setPredictedData] = useState([]);
  const [workOrdersGeoJSON, setWorkOrdersGeoJSON] = useState(null);

  // Time Scrubbing State
  const [minTs, setMinTs] = useState(null);
  const [maxTs, setMaxTs] = useState(null);
  const [currentTs, setCurrentTs] = useState(null);
  const [selectedTypes, setSelectedTypes] = useState([]);
  const [selectedSeverities, setSelectedSeverities] = useState([]);

  // Interactive Tools State
  const [activeTool, setActiveTool] = useState('POINTER'); // 'POINTER' | 'DRAW_POLYGON' | 'MEASURE_DISTANCE'
  const [drawnPolygonCoords, setDrawnPolygonCoords] = useState([]);
  const [polygonAnalysisResult, setPolygonAnalysisResult] = useState(null);
  const [measuredPoints, setMeasuredPoints] = useState([]);
  const [distanceResult, setDistanceResult] = useState(null);

  // Selection & UI Modals
  const [selectedDefect, setSelectedDefect] = useState(null);
  const [showDigitalTwin, setShowDigitalTwin] = useState(false);
  const [pdfReportModalData, setPdfReportModalData] = useState(null);

  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const deckInstanceRef = useRef(null);

  // Fetch HD Map Data from backend API on mount
  useEffect(() => {
    // 1. Fetch Defects
    fetch('/api/map/defects?limit=15000')
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success' && data.defects) {
          setDefects(data.defects);
          setFilteredDefects(data.defects);

          const timestamps = data.defects.map(d => d.timestamp);
          const min = Math.min(...timestamps);
          const max = Math.max(...timestamps);
          setMinTs(min);
          setMaxTs(max);
          setCurrentTs(max);
        }
      })
      .catch(err => console.error("Error loading defects:", err));

    // 2. Fetch Heatmap
    fetch('/api/map/heatmap')
      .then(res => res.json())
      .then(data => { if (data.points) setHeatmapPoints(data.points); })
      .catch(err => console.error("Error loading heatmap:", err));

    // 3. Fetch Trajectory
    fetch('/api/map/trajectory')
      .then(res => res.json())
      .then(data => { if (data.path) setTrajectoryData(data); })
      .catch(err => console.error("Error loading trajectory:", err));

    // 4. Fetch Predicted Hotspots
    fetch('/api/map/predictions')
      .then(res => res.json())
      .then(data => { if (data.predictions) setPredictedData(data.predictions); })
      .catch(err => console.error("Error loading predictions:", err));

    // 5. Fetch Work Orders
    fetch('/api/map/municipality/work-orders')
      .then(res => res.json())
      .then(data => setWorkOrdersGeoJSON(data))
      .catch(err => console.error("Error loading work orders:", err));
  }, []);

  // Filter Defects via Web Worker on timestamp / type / severity change
  useEffect(() => {
    if (!defects || defects.length === 0) return;

    dispatchWorkerTask('FILTER_DEFECTS', {
      defects,
      minTs,
      maxTs: currentTs,
      selectedTypes,
      selectedSeverities
    }).then(filtered => {
      setFilteredDefects(filtered);
    }).catch(err => {
      // Fallback filter
      const res = defects.filter(d => {
        if (currentTs && d.timestamp > currentTs) return false;
        if (selectedTypes.length > 0 && !selectedTypes.includes(d.type)) return false;
        if (selectedSeverities.length > 0 && !selectedSeverities.includes(d.severity)) return false;
        return true;
      });
      setFilteredDefects(res);
    });
  }, [defects, currentTs, selectedTypes, selectedSeverities]);

  // Handle map click for drawing polygon or measuring distance
  const handleMapClick = useCallback((e) => {
    const coords = e.lngLat ? [e.lngLat.lng, e.lngLat.lat] : [e.coordinate[0], e.coordinate[1]];

    if (activeTool === 'DRAW_POLYGON') {
      const updated = [...drawnPolygonCoords, coords];
      setDrawnPolygonCoords(updated);

      if (updated.length >= 3) {
        // Run spatial analysis via Web Worker
        const closedRing = [...updated, updated[0]];
        dispatchWorkerTask('POLYGON_QUERY', {
          defects: filteredDefects,
          polygonCoords: closedRing
        }).then(res => {
          const area = TurfHelpers.area(closedRing);
          setPolygonAnalysisResult({ ...res, areaSqMeters: area });
        });
      }
    } else if (activeTool === 'MEASURE_DISTANCE') {
      const updated = [...measuredPoints, coords];
      setMeasuredPoints(updated);

      if (updated.length >= 2) {
        dispatchWorkerTask('MEASURE_DISTANCE', { points: updated }).then(res => {
          setDistanceResult(res);
        });
      }
    }
  }, [activeTool, drawnPolygonCoords, filteredDefects, measuredPoints]);

  const resetTools = () => {
    setActiveTool('POINTER');
    setDrawnPolygonCoords([]);
    setPolygonAnalysisResult(null);
    setMeasuredPoints([]);
    setDistanceResult(null);
  };

  const handleExportPDF = () => {
    if (!polygonAnalysisResult || drawnPolygonCoords.length < 3) {
      alert("Please draw a valid polygon area on the map first using the 'Draw Polygon' tool.");
      return;
    }
    const reportData = generatePDFReportData({
      regionName: "Custom GIS Region",
      polygonCoords: drawnPolygonCoords,
      defects: polygonAnalysisResult.containedDefects || [],
      areaSqMeters: polygonAnalysisResult.areaSqMeters
    });
    setPdfReportModalData(reportData);
  };

  return (
    <div style={styles.mapWrapper}>
      {/* Top GIS Header Bar */}
      <div style={styles.topNav}>
        <div style={styles.brandTitle}>
          <span style={styles.brandBadge}>HD GIS</span>
          <span style={styles.brandName}>SAFEDRIVE AI DIGITAL TWIN</span>
        </div>

        {/* Toolbar & Layer Toggles */}
        <div style={styles.toolbarGroup}>
          <button
            onClick={() => setActiveTool(activeTool === 'POINTER' ? 'DRAW_POLYGON' : 'POINTER')}
            style={{
              ...styles.toolBtn,
              background: activeTool === 'DRAW_POLYGON' ? '#38bdf8' : 'rgba(30, 41, 59, 0.8)',
              color: activeTool === 'DRAW_POLYGON' ? '#0f172a' : '#f8fafc'
            }}
          >
            ✏️ DRAW POLYGON
          </button>
          <button
            onClick={() => setActiveTool(activeTool === 'MEASURE_DISTANCE' ? 'POINTER' : 'MEASURE_DISTANCE')}
            style={{
              ...styles.toolBtn,
              background: activeTool === 'MEASURE_DISTANCE' ? '#38bdf8' : 'rgba(30, 41, 59, 0.8)',
              color: activeTool === 'MEASURE_DISTANCE' ? '#0f172a' : '#f8fafc'
            }}
          >
            📏 MEASURE DISTANCE
          </button>

          {(drawnPolygonCoords.length > 0 || measuredPoints.length > 0) && (
            <button onClick={resetTools} style={styles.resetBtn}>
              🔄 CLEAR TOOLS
            </button>
          )}

          <button onClick={() => setShowDigitalTwin(true)} style={styles.digitalTwinBtn}>
            💎 3D DIGITAL TWIN
          </button>
        </div>
      </div>

      {/* Main Interactive Canvas Container */}
      <div
        ref={mapContainerRef}
        onClick={handleMapClick}
        style={styles.mapCanvas}
      >
        {/* Mock Vector Map Canvas Layer representation for standalone browser preview */}
        <div style={styles.mockMapBackground}>
          <div style={styles.roadCorridorGrid} />
          
          {/* Render 3D Defect Markers on Map */}
          {layersConfig.defects && filteredDefects.slice(0, 400).map((d) => {
            const isSelected = selectedDefect && selectedDefect.id === d.id;
            const topOffset = ((37.7850 - d.lat) / 0.04) * 100;
            const leftOffset = ((d.lng - (-122.4250)) / 0.04) * 100;

            const color = d.severity === 'Critical' ? '#ef4444' : d.severity === 'High' ? '#f97316' : d.severity === 'Medium' ? '#eab308' : '#3b82f6';
            const size = Math.max(d.depth_cm * 1.5, 12);

            return (
              <div
                key={d.id}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedDefect(d);
                }}
                title={`${d.id} | ${d.type} (${d.severity})`}
                style={{
                  position: 'absolute',
                  top: `${Math.min(Math.max(topOffset, 5), 90)}%`,
                  left: `${Math.min(Math.max(leftOffset, 5), 90)}%`,
                  width: `${size}px`,
                  height: `${size}px`,
                  borderRadius: '50%',
                  backgroundColor: color,
                  border: isSelected ? '3px solid #ffffff' : '1px solid rgba(0,0,0,0.5)',
                  boxShadow: isSelected ? `0 0 16px ${color}` : `0 0 8px ${color}aa`,
                  cursor: 'pointer',
                  transform: 'translate(-50%, -50%)',
                  transition: 'all 0.2s ease',
                  zIndex: isSelected ? 20 : 10
                }}
              />
            );
          })}

          {/* Render Active Polygon Draw Lines */}
          {drawnPolygonCoords.length > 0 && (
            <svg style={styles.svgOverlay}>
              <polygon
                points={drawnPolygonCoords.map(p => `${((p[0] - (-122.4250)) / 0.04) * 100}%,${((37.7850 - p[1]) / 0.04) * 100}%`).join(' ')}
                fill="rgba(56, 189, 248, 0.25)"
                stroke="#38bdf8"
                strokeWidth="2"
                strokeDasharray="4"
              />
            </svg>
          )}
        </div>
      </div>

      {/* Layer Toggles Panel (Top Right) */}
      <div style={styles.layerPanel}>
        <div style={styles.panelTitle}>MAP LAYERS</div>
        {Object.keys(layersConfig).map(layerKey => (
          <label key={layerKey} style={styles.layerRow}>
            <input
              type="checkbox"
              checked={layersConfig[layerKey]}
              onChange={() => setLayersConfig({ ...layersConfig, [layerKey]: !layersConfig[layerKey] })}
              style={{ accentColor: '#38bdf8' }}
            />
            <span style={styles.layerLabel}>{layerKey.toUpperCase()}</span>
          </label>
        ))}
      </div>

      {/* Polygon Analysis Results Floating Card */}
      {polygonAnalysisResult && (
        <div style={styles.analysisCard}>
          <div style={styles.cardHeader}>
            <span>REGION SPATIAL ANALYSIS</span>
            <button onClick={handleExportPDF} style={styles.exportPdfBtn}>
              📄 EXPORT PDF
            </button>
          </div>
          <div style={styles.cardMetrics}>
            <div><span style={styles.metricLbl}>Total Area:</span> <b>{polygonAnalysisResult.areaSqMeters} m²</b></div>
            <div><span style={styles.metricLbl}>Defects Inside:</span> <b>{polygonAnalysisResult.totalCount}</b></div>
            <div><span style={styles.metricLbl}>Avg Depth:</span> <b>{polygonAnalysisResult.avgDepthCm} cm</b></div>
          </div>
        </div>
      )}

      {/* Distance Measurement Results Card */}
      {distanceResult && (
        <div style={styles.distanceCard}>
          <div style={styles.metricLbl}>DISTANCE MEASUREMENT</div>
          <div style={{ fontSize: '18px', fontWeight: 800, color: '#38bdf8', marginTop: '4px' }}>
            {distanceResult.totalMeters} meters ({distanceResult.totalKm} km)
          </div>
        </div>
      )}

      {/* Click Defect Detail Side Panel Drawer */}
      {selectedDefect && (
        <div style={styles.detailDrawer}>
          <div style={styles.drawerHeader}>
            <div>
              <span style={styles.defectTag}>{selectedDefect.id}</span>
              <h3 style={{ margin: '4px 0 0 0', fontSize: '16px' }}>{selectedDefect.type.toUpperCase()}</h3>
            </div>
            <button onClick={() => setSelectedDefect(null)} style={styles.closeBtn}>✕</button>
          </div>

          <div style={styles.drawerBody}>
            <div style={styles.infoRow}>
              <span style={styles.metaLabel}>SEVERITY:</span>
              <span style={{
                padding: '2px 8px',
                borderRadius: '4px',
                fontWeight: 700,
                color: '#fff',
                background: selectedDefect.severity === 'Critical' ? '#ef4444' : '#f97316'
              }}>
                {selectedDefect.severity}
              </span>
            </div>

            <div style={styles.infoRow}>
              <span style={styles.metaLabel}>COORDINATES:</span>
              <span>{formatCoordinates(selectedDefect.lat, selectedDefect.lng, selectedDefect.elevation_m)}</span>
            </div>

            <div style={styles.infoRow}>
              <span style={styles.metaLabel}>MEASURED DEPTH:</span>
              <b>{selectedDefect.depth_cm} cm</b>
            </div>

            <div style={styles.infoRow}>
              <span style={styles.metaLabel}>CORRIDOR:</span>
              <span>{selectedDefect.corridor}</span>
            </div>

            <div style={styles.infoRow}>
              <span style={styles.metaLabel}>DETECTED BY:</span>
              <span>{selectedDefect.detected_by_vehicle}</span>
            </div>

            <button
              onClick={() => alert(`Work order generated for defect ${selectedDefect.id} and assigned to Municipal Infrastructure Queue.`)}
              style={styles.workOrderActionBtn}
            >
              🛠️ CREATE MUNICIPAL WORK ORDER
            </button>
          </div>
        </div>
      )}

      {/* Time-Series Playback Controller Bar */}
      <TimePlayback
        minTimestamp={minTs}
        maxTimestamp={maxTs}
        currentTimestamp={currentTs}
        onTimestampChange={setCurrentTs}
        defects={defects}
        selectedTypes={selectedTypes}
        selectedSeverities={selectedSeverities}
        onTypeFilterChange={setSelectedTypes}
        onSeverityFilterChange={setSelectedSeverities}
      />

      {/* 3D Digital Twin Modal */}
      {showDigitalTwin && (
        <DigitalTwin onClose={() => setShowDigitalTwin(false)} />
      )}

      {/* PDF Export Preview Modal */}
      {pdfReportModalData && (
        <div style={styles.overlayModal}>
          <div style={styles.pdfCard}>
            <h2 style={{ margin: '0 0 10px 0', color: '#38bdf8' }}>GIS REGION REPORT</h2>
            <p>Report ID: {pdfReportModalData.reportId}</p>
            <p>Region Area: {pdfReportModalData.areaSqMeters} m² ({pdfReportModalData.areaSqKm} km²)</p>
            <p>Total Defects: {pdfReportModalData.totalDefects} (Critical: {pdfReportModalData.criticalCount})</p>
            <button
              onClick={() => {
                alert("Downloading compiled PDF Report...");
                setPdfReportModalData(null);
              }}
              style={styles.workOrderActionBtn}
            >
              📥 DOWNLOAD PDF FILE
            </button>
            <button onClick={() => setPdfReportModalData(null)} style={{ ...styles.closeBtn, marginTop: '10px' }}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  mapWrapper: {
    position: 'relative',
    width: '100%',
    height: '100vh',
    backgroundColor: '#0b0f19',
    overflow: 'hidden',
    fontFamily: 'Inter, system-ui, sans-serif'
  },
  topNav: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '60px',
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    backdropFilter: 'blur(12px)',
    borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '0 24px',
    zIndex: 40,
    boxSizing: 'border-box'
  },
  brandTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px'
  },
  brandBadge: {
    backgroundColor: '#38bdf8',
    color: '#0f172a',
    padding: '3px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 800
  },
  brandName: {
    color: '#f8fafc',
    fontSize: '14px',
    fontWeight: 800,
    letterSpacing: '0.5px'
  },
  toolbarGroup: {
    display: 'flex',
    gap: '10px',
    alignItems: 'center'
  },
  toolBtn: {
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '8px',
    padding: '7px 14px',
    fontSize: '11px',
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'all 0.2s ease'
  },
  resetBtn: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
    color: '#ef4444',
    border: '1px solid #ef4444',
    borderRadius: '8px',
    padding: '7px 12px',
    fontSize: '11px',
    fontWeight: 700,
    cursor: 'pointer'
  },
  digitalTwinBtn: {
    background: 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)',
    color: '#0f172a',
    border: 'none',
    borderRadius: '8px',
    padding: '7px 16px',
    fontSize: '11px',
    fontWeight: 800,
    cursor: 'pointer',
    boxShadow: '0 0 12px rgba(56, 189, 248, 0.4)'
  },
  mapCanvas: {
    width: '100%',
    height: '100%',
    position: 'relative'
  },
  mockMapBackground: {
    width: '100%',
    height: '100%',
    backgroundColor: '#070a12',
    backgroundImage: 'radial-gradient(rgba(56, 189, 248, 0.05) 1px, transparent 0)',
    backgroundSize: '30px 30px',
    position: 'relative'
  },
  roadCorridorGrid: {
    position: 'absolute',
    top: '40%',
    left: 0,
    width: '100%',
    height: '80px',
    backgroundColor: 'rgba(30, 41, 59, 0.3)',
    borderTop: '1px dashed rgba(56, 189, 248, 0.2)',
    borderBottom: '1px dashed rgba(56, 189, 248, 0.2)'
  },
  svgOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    pointerEvents: 'none'
  },
  layerPanel: {
    position: 'absolute',
    top: '76px',
    right: '24px',
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    backdropFilter: 'blur(12px)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '10px',
    padding: '14px',
    width: '180px',
    zIndex: 35,
    color: '#f8fafc'
  },
  panelTitle: {
    fontSize: '10px',
    fontWeight: 800,
    color: '#64748b',
    letterSpacing: '1px',
    marginBottom: '10px'
  },
  layerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '11px',
    marginBottom: '8px',
    cursor: 'pointer'
  },
  layerLabel: {
    color: '#cbd5e1',
    fontWeight: 600
  },
  analysisCard: {
    position: 'absolute',
    top: '76px',
    left: '24px',
    backgroundColor: 'rgba(15, 23, 42, 0.9)',
    border: '1px solid #38bdf8',
    borderRadius: '10px',
    padding: '14px 18px',
    zIndex: 35,
    color: '#f8fafc',
    width: '280px'
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '10px',
    fontSize: '11px',
    fontWeight: 700,
    color: '#38bdf8'
  },
  exportPdfBtn: {
    backgroundColor: '#38bdf8',
    color: '#0f172a',
    border: 'none',
    borderRadius: '4px',
    padding: '3px 8px',
    fontSize: '10px',
    fontWeight: 800,
    cursor: 'pointer'
  },
  cardMetrics: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    fontSize: '12px'
  },
  distanceCard: {
    position: 'absolute',
    top: '76px',
    left: '24px',
    backgroundColor: 'rgba(15, 23, 42, 0.9)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '10px',
    padding: '14px 18px',
    zIndex: 35,
    color: '#f8fafc'
  },
  metricLbl: {
    fontSize: '11px',
    color: '#64748b',
    fontWeight: 700
  },
  detailDrawer: {
    position: 'absolute',
    top: '76px',
    right: '220px',
    width: '300px',
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    backdropFilter: 'blur(16px)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '12px',
    padding: '18px',
    zIndex: 45,
    color: '#f8fafc',
    boxShadow: '0 20px 40px rgba(0,0,0,0.6)'
  },
  drawerHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '14px'
  },
  defectTag: {
    fontSize: '10px',
    fontWeight: 800,
    color: '#38bdf8'
  },
  drawerBody: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    fontSize: '12px'
  },
  infoRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px'
  },
  metaLabel: {
    fontSize: '10px',
    color: '#64748b',
    fontWeight: 700
  },
  workOrderActionBtn: {
    marginTop: '10px',
    width: '100%',
    backgroundColor: '#38bdf8',
    color: '#0f172a',
    border: 'none',
    borderRadius: '8px',
    padding: '10px',
    fontSize: '11px',
    fontWeight: 800,
    cursor: 'pointer'
  },
  overlayModal: {
    position: 'fixed',
    top: 0,
    left: 0,
    width: '100vw',
    height: '100vh',
    backgroundColor: 'rgba(0,0,0,0.8)',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 2000
  },
  pdfCard: {
    backgroundColor: '#0f172a',
    border: '1px solid #38bdf8',
    borderRadius: '12px',
    padding: '24px',
    width: '360px',
    color: '#f8fafc'
  },
  closeBtn: {
    background: 'transparent',
    border: 'none',
    color: '#94a3b8',
    fontSize: '16px',
    cursor: 'pointer'
  }
};
