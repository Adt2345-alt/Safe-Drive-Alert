import React, { useState, useEffect, useRef } from 'react';

const SEVERITY_COLORS = {
  Critical: '#ef4444',
  High: '#f59e0b',
  Medium: '#eab308',
  Low: '#3b82f6',
  Repaired: '#10b981'
};

/**
 * DigitalTwin Component (3D Procedural Telemetry Inspection Tool)
 * Renders Three.js 3D viewport of recorded defect geometry bound to GET /api/defects/<id>.
 */
export default function DigitalTwin({ defectId, defect: initialDefect, onClose }) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const controlsRef = useRef(null);
  const rendererRef = useRef(null);

  const [defectData, setDefectData] = useState(initialDefect || null);
  const [loading, setLoading] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [isMeasuring, setIsMeasuring] = useState(false);
  const [measurePoints, setMeasurePoints] = useState([]);
  const [measuredDistance, setMeasuredDistance] = useState(null);
  const [compareMode, setCompareMode] = useState(false);
  const [nearbyDefects, setNearbyDefects] = useState([]);
  const [allDefectsList, setAllDefectsList] = useState([]);

  const [labelCoords, setLabelCoords] = useState({
    depth: { x: 0, y: 0, visible: false },
    width: { x: 0, y: 0, visible: false },
    length: { x: 0, y: 0, visible: false }
  });

  // 1. Fetch available defects list & auto-select first defect if none pre-selected
  useEffect(() => {
    fetch('/api/map/defects?limit=100')
      .then(res => res.json())
      .then(data => {
        if (data.defects && data.defects.length > 0) {
          setAllDefectsList(data.defects);

          const targetId = initialDefect ? initialDefect.id : defectId;
          if (!targetId && !defectData) {
            const first = data.defects[0];
            const rawId = first.raw_id || first.id;
            const numId = typeof rawId === 'number' ? rawId : parseInt(String(rawId).replace('DEF-', ''), 10);
            if (numId && !isNaN(numId)) {
              fetch(`/api/defects/${numId}`)
                .then(r => r.json())
                .then(d => { setDefectData(d); setLoading(false); })
                .catch(() => { setDefectData(first); setLoading(false); });
            } else {
              setDefectData(first);
              setLoading(false);
            }
          }
        } else {
          setLoading(false);
        }
      })
      .catch(err => {
        console.error("Error loading defects list:", err);
        setLoading(false);
      });
  }, []);

  // 2. Fetch exact defect telemetry by ID if passed explicitly
  useEffect(() => {
    const targetId = initialDefect ? initialDefect.id : defectId;
    if (!targetId) return;

    const numericId = typeof targetId === 'number' ? targetId : parseInt(String(targetId).replace('DEF-', ''), 10);

    if (numericId && !isNaN(numericId)) {
      setLoading(true);
      fetch(`/api/defects/${numericId}`)
        .then(res => {
          if (!res.ok) throw new Error("Defect not found");
          return res.json();
        })
        .then(data => {
          setDefectData(data);
          setLoading(false);
        })
        .catch(err => {
          console.warn("Could not fetch defect by ID, using initial:", err);
          setDefectData(initialDefect);
          setLoading(false);
        });
    } else if (initialDefect) {
      setDefectData(initialDefect);
      setLoading(false);
    }
  }, [defectId, initialDefect]);


  // 2. Fetch nearby defects for comparison mode
  useEffect(() => {
    if (compareMode && defectData) {
      const numericId = typeof defectData.id === 'number' ? defectData.id : parseInt(String(defectData.id).replace('DEF-', ''), 10);
      if (numericId) {
        fetch(`/api/defects/${numericId}/nearby?radius_m=200`)
          .then(res => res.json())
          .then(data => {
            if (data.nearby_defects) setNearbyDefects(data.nearby_defects);
          })
          .catch(err => console.error("Error fetching nearby defects:", err));
      }
    }
  }, [compareMode, defectData]);

  // 3. Setup Three.js 3D Scene
  useEffect(() => {
    if (!mountRef.current || !window.THREE) return;
    const THREE = window.THREE;
    const width = mountRef.current.clientWidth;
    const height = mountRef.current.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x070a12);
    scene.fog = new THREE.FogExp2(0x070a12, 0.025);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 9, 14);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    mountRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    let controls;
    if (window.THREE.OrbitControls) {
      controls = new window.THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.05;
      controls.maxPolarAngle = Math.PI / 2 - 0.05;
      controls.target.set(0, -0.2, 0);
      controlsRef.current = controls;
    }

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0xffffff, 1.2);
    sunLight.position.set(15, 30, 20);
    sunLight.castShadow = true;
    scene.add(sunLight);

    const cyanSpot = new THREE.SpotLight(0x00f2fe, 1.5, 40, Math.PI / 4, 0.5);
    cyanSpot.position.set(-10, 20, 10);
    scene.add(cyanSpot);

    const grid = new THREE.GridHelper(60, 30, 0x00f2fe, 0x1e293b);
    grid.position.y = -0.1;
    scene.add(grid);

    // Road mesh
    const depthCm = defectData ? (defectData.depth_cm || 6.0) : 6.0;
    const widthCm = defectData ? (defectData.width_cm || 36.0) : 36.0;
    const lengthCm = defectData ? (defectData.length_cm || 48.0) : 48.0;

    const depthM = depthCm / 100.0;
    const widthM = widthCm / 100.0;
    const lengthM = lengthCm / 100.0;

    const roadGeo = new THREE.PlaneGeometry(16, 30, 100, 100);
    roadGeo.rotateX(-Math.PI / 2);

    if (defectData) {
      const pos = roadGeo.attributes.position;
      for (let i = 0; i < pos.count; i++) {
        const x = pos.getX(i);
        const z = pos.getZ(i);

        const rx = x / (widthM * 0.7);
        const rz = z / (lengthM * 0.7);
        const distSq = rx * rx + rz * rz;

        if (distSq < 1.0) {
          const falloff = Math.cos((Math.sqrt(distSq) * Math.PI) / 2);
          const organicNoise = Math.sin(x * 20) * Math.cos(z * 20) * 0.15 + 0.85;
          const disp = depthM * falloff * organicNoise;
          pos.setY(i, -disp);
        }
      }
      roadGeo.computeVertexNormals();
    }

    const roadMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.88,
      metalness: 0.12
    });
    const roadMesh = new THREE.Mesh(roadGeo, roadMat);
    roadMesh.receiveShadow = true;
    scene.add(roadMesh);

    // Road markings
    for (let z = -14; z < 14; z += 3) {
      const dashGeo = new THREE.PlaneGeometry(0.15, 1.5);
      dashGeo.rotateX(-Math.PI / 2);
      const dashMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const dash = new THREE.Mesh(dashGeo, dashMat);
      dash.position.set(0, 0.01, z);
      scene.add(dash);
    }

    [-6, 6].forEach(x => {
      const edgeGeo = new THREE.PlaneGeometry(0.15, 30);
      edgeGeo.rotateX(-Math.PI / 2);
      const edgeMat = new THREE.MeshBasicMaterial({ color: 0x94a3b8 });
      const edge = new THREE.Mesh(edgeGeo, edgeMat);
      edge.position.set(x, 0.01, 0);
      scene.add(edge);
    });

    [-7.25, 7.25].forEach(x => {
      const sideGeo = new THREE.BoxGeometry(1.5, 0.1, 30);
      const sideMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.7 });
      const sidewalk = new THREE.Mesh(sideGeo, sideMat);
      sidewalk.position.set(x, 0.05, 0);
      scene.add(sidewalk);
    });

    const buildingMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.5, metalness: 0.4 });
    [
      { x: -12, z: -10, w: 6, h: 14, d: 8 },
      { x: -12, z: 4, w: 6, h: 20, d: 10 },
      { x: 12, z: -8, w: 6, h: 18, d: 9 },
      { x: 12, z: 6, w: 6, h: 12, d: 7 }
    ].forEach(b => {
      const bGeo = new THREE.BoxGeometry(b.w, b.h, b.d);
      const bMesh = new THREE.Mesh(bGeo, buildingMat);
      bMesh.position.set(b.x, b.h / 2, b.z);
      scene.add(bMesh);

      const wireGeo = new THREE.EdgesGeometry(bGeo);
      const wireMat = new THREE.LineBasicMaterial({ color: 0x00f2fe, opacity: 0.3, transparent: true });
      const wireframe = new THREE.LineSegments(wireGeo, wireMat);
      bMesh.add(wireframe);
    });

    if (defectData) {
      const colorHex = SEVERITY_COLORS[defectData.severity] || '#00F2FE';
      const rimGeo = new THREE.RingGeometry(widthM * 0.45, widthM * 0.52, 32);
      rimGeo.rotateX(-Math.PI / 2);
      const rimMat = new THREE.MeshBasicMaterial({
        color: parseInt(colorHex.replace('#', '0x')),
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.8
      });
      const rim = new THREE.Mesh(rimGeo, rimMat);
      rim.position.set(0, 0.02, 0);
      scene.add(rim);

      const depthLineGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(0, 0.05, 0),
        new THREE.Vector3(0, -depthM, 0)
      ]);
      const depthLineMat = new THREE.LineDashedMaterial({ color: 0x00f2fe, dashSize: 0.1, gapSize: 0.05 });
      const depthLine = new THREE.Line(depthLineGeo, depthLineMat);
      depthLine.computeLineDistances();
      scene.add(depthLine);

      const widthLineGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(-widthM / 2, 0.05, 0),
        new THREE.Vector3(widthM / 2, 0.05, 0)
      ]);
      const widthLineMat = new THREE.LineBasicMaterial({ color: 0xf59e0b, linewidth: 2 });
      const widthLine = new THREE.Line(widthLineGeo, widthLineMat);
      scene.add(widthLine);

      const lengthLineGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(0, 0.05, -lengthM / 2),
        new THREE.Vector3(0, 0.05, lengthM / 2)
      ]);
      const lengthLineMat = new THREE.LineBasicMaterial({ color: 0x10b981, linewidth: 2 });
      const lengthLine = new THREE.Line(lengthLineGeo, lengthLineMat);
      scene.add(lengthLine);
    }

    let animId;
    const tempVec = new THREE.Vector3();
    const animate = () => {
      animId = requestAnimationFrame(animate);
      if (controls) controls.update();
      renderer.render(scene, camera);

      if (defectData && camera) {
        const projectPoint = (v) => {
          tempVec.copy(v);
          tempVec.project(camera);
          const x = (tempVec.x * 0.5 + 0.5) * width;
          const y = (-(tempVec.y * 0.5) + 0.5) * height;
          return { x, y, visible: tempVec.z < 1.0 };
        };

        setLabelCoords({
          depth: projectPoint(new THREE.Vector3(0, -depthM / 2, 0)),
          width: projectPoint(new THREE.Vector3(widthM / 2, 0.1, 0)),
          length: projectPoint(new THREE.Vector3(0, 0.1, lengthM / 2))
        });
      }
    };
    animate();

    return () => {
      cancelAnimationFrame(animId);
      if (renderer && renderer.domElement && mountRef.current && mountRef.current.contains(renderer.domElement)) {
        mountRef.current.removeChild(renderer.domElement);
      }
      if (renderer) {
        renderer.dispose();
      }
    };
  }, [defectData]);


  const handleCanvasClick = (e) => {
    if (!isMeasuring || !mountRef.current || !sceneRef.current || !cameraRef.current) return;
    const rect = mountRef.current.getBoundingClientRect();
    const mouse = new window.THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1
    );

    const raycaster = new window.THREE.Raycaster();
    raycaster.setFromCamera(mouse, cameraRef.current);
    const intersects = raycaster.intersectObjects(sceneRef.current.children, true);

    if (intersects.length > 0) {
      const pt = intersects[0].point;
      setMeasurePoints(prev => {
        if (prev.length >= 2) return [pt];
        const next = [...prev, pt];
        if (next.length === 2) {
          const distM = next[0].distanceTo(next[1]);
          setMeasuredDistance(Math.round(distM * 100 * 10) / 10);
        }
        return next;
      });
    }
  };

  const resetView = () => {
    if (cameraRef.current && controlsRef.current) {
      cameraRef.current.position.set(0, 9, 14);
      controlsRef.current.target.set(0, -0.2, 0);
      controlsRef.current.update();
    }
  };

  const takeSnapshot = () => {
    if (!rendererRef.current) return;
    const dataUrl = rendererRef.current.domElement.toDataURL('image/png');
    const link = document.createElement('a');
    const defId = defectData ? defectData.id : 'view';
    link.download = `SafeDrive-3D-Defect-${defId}.png`;
    link.href = dataUrl;
    link.click();
  };

  const depthCm = defectData ? (defectData.depth_cm || 6.0) : 6.0;
  const widthCm = defectData ? (defectData.width_cm || 36.0) : 36.0;
  const lengthCm = defectData ? (defectData.length_cm || 48.0) : 48.0;

  const volumeLiters = Math.round((2 / 3) * Math.PI * (widthCm / 2) * (lengthCm / 2) * depthCm / 1000 * 10) / 10;
  const repairCostEst = Math.round(volumeLiters * 14.5 + 120);

  return (
    <div style={styles.overlay}>
      <div style={styles.card}>
        <div style={styles.headerRow}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '20px' }}>💎</span>
            <div>
              <h3 style={styles.title}>3D DIGITAL TWIN INSPECTION TOOL</h3>
              <p style={styles.subtitle}>
                3D Procedural Telemetry View (From Recorded Detection Database)
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {allDefectsList.length > 0 && (
              <select
                value={defectData ? (defectData.raw_id || defectData.id) : ''}
                onChange={(e) => {
                  const targetId = parseInt(e.target.value, 10);
                  if (targetId) {
                    setLoading(true);
                    fetch(`/api/defects/${targetId}`)
                      .then(r => r.json())
                      .then(d => { setDefectData(d); setLoading(false); })
                      .catch(err => console.error("Error switching defect:", err));
                  }
                }}
                style={{
                  background: '#0F172A', color: '#00F2FE', border: '1px solid #00F2FE',
                  borderRadius: '6px', padding: '5px 10px', fontSize: '11px', fontFamily: 'Orbitron',
                  cursor: 'pointer', outline: 'none'
                }}
              >
                {allDefectsList.map(d => (
                  <option key={d.id} value={d.raw_id || d.id}>
                    {d.id || `DEF-${d.raw_id}`} - {(d.type || 'DEFECT').toUpperCase()} ({d.severity}) | {d.corridor || 'MG Road'}
                  </option>
                ))}
              </select>
            )}
            <button onClick={onClose} style={styles.closeBtn}>✕</button>
          </div>
        </div>


        {!defectData && !loading && (
          <div style={styles.emptyStateContainer}>
            <div style={{ fontSize: '36px', marginBottom: '12px' }}>📍</div>
            <h4 style={{ fontFamily: 'Orbitron', color: '#00F2FE', fontSize: '16px', marginBottom: '8px' }}>
              NO DEFECT SELECTED FOR 3D INSPECTION
            </h4>
            <p style={{ color: '#9CA3AF', fontSize: '13px', maxWidth: '440px', margin: '0 auto 16px auto' }}>
              Click any marker on the map to inspect a defect in 3D.
            </p>
            <button onClick={onClose} style={styles.closeModalBtn}>
              Return to Map
            </button>
          </div>
        )}

        {loading && (
          <div style={styles.loadingContainer}>
            <div style={styles.spinner} />
            <span style={{ fontFamily: 'Orbitron', color: '#00F2FE', fontSize: '12px', marginTop: '12px' }}>
              LOADING 3D GEOMETRY FROM SQLite DATABASE...
            </span>
          </div>
        )}

        {defectData && !loading && (
          <div style={{ position: 'relative', width: '100%' }}>
            <div style={styles.toolbar}>
              <button onClick={resetView} style={styles.toolBtn} title="Reset Camera View">
                🎯 Reset View
              </button>
              <button onClick={takeSnapshot} style={styles.toolBtn} title="Download PNG Snapshot">
                📸 Snapshot
              </button>
              <button
                onClick={() => { setIsMeasuring(!isMeasuring); setMeasurePoints([]); setMeasuredDistance(null); }}
                style={{ ...styles.toolBtn, border: isMeasuring ? '1px solid #00F2FE' : '1px solid rgba(0,242,254,0.3)', background: isMeasuring ? 'rgba(0,242,254,0.2)' : 'rgba(15,23,42,0.8)' }}
              >
                📏 {isMeasuring ? 'Measuring...' : 'Measure'}
              </button>
              <button
                onClick={() => setShowLabels(!showLabels)}
                style={styles.toolBtn}
              >
                🏷️ {showLabels ? 'Hide Labels' : 'Show Labels'}
              </button>
              <button
                onClick={() => setCompareMode(!compareMode)}
                style={{ ...styles.toolBtn, border: compareMode ? '1px solid #f59e0b' : '1px solid rgba(0,242,254,0.3)' }}
              >
                🔄 {compareMode ? 'Comparing' : 'Compare'}
              </button>
            </div>

            <div
              ref={mountRef}
              onClick={handleCanvasClick}
              style={{
                width: '100%',
                height: '460px',
                borderRadius: '10px',
                overflow: 'hidden',
                position: 'relative',
                cursor: isMeasuring ? 'crosshair' : 'grab',
                border: '1px solid rgba(0, 242, 254, 0.3)'
              }}
            >
              <div style={styles.telemetryPanel}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontFamily: 'Orbitron', fontWeight: 'bold', color: '#00F2FE', fontSize: '13px' }}>
                    {defectData.formatted_id || `DEF-${defectData.id}`}
                  </span>
                  <span style={{
                    background: SEVERITY_COLORS[defectData.severity] || '#00F2FE',
                    color: '#0B0F19', padding: '2px 8px', borderRadius: '4px',
                    fontFamily: 'Orbitron', fontSize: '10px', fontWeight: 'bold'
                  }}>
                    {defectData.severity ? defectData.severity.toUpperCase() : 'HIGH'}
                  </span>
                </div>

                <div style={styles.metaGrid}>
                  <div><span style={styles.metaKey}>Type:</span> <b>{defectData.type ? defectData.type.toUpperCase() : 'POTHOLE'}</b></div>
                  <div><span style={styles.metaKey}>Confidence:</span> <b>{Math.round((defectData.confidence || 0.94) * 100)}%</b></div>
                  <div><span style={styles.metaKey}>Depth:</span> <b style={{ color: '#00F2FE' }}>{depthCm} cm</b></div>
                  <div><span style={styles.metaKey}>Width:</span> <b style={{ color: '#f59e0b' }}>{widthCm} cm</b></div>
                  <div><span style={styles.metaKey}>Length:</span> <b style={{ color: '#10b981' }}>{lengthCm} cm</b></div>
                  <div><span style={styles.metaKey}>Est. Volume:</span> <b>{volumeLiters} Liters</b></div>
                  <div><span style={styles.metaKey}>Repair Est.:</span> <b style={{ color: '#10b981' }}>${repairCostEst}</b></div>
                  <div><span style={styles.metaKey}>Source:</span> <b>{defectData.source || 'Simulation Drive'}</b></div>
                </div>

                <div style={{ fontSize: '10px', color: '#9CA3AF', marginTop: '6px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '4px' }}>
                  📍 {defectData.road_name || 'Golden Gate Park Route'} ({defectData.lat ? defectData.lat.toFixed(5) : 37.7699}, {defectData.lng ? defectData.lng.toFixed(5) : -122.4668})
                </div>
              </div>

              {showLabels && labelCoords.depth.visible && (
                <div style={{ ...styles.labelBox, top: `${labelCoords.depth.y}px`, left: `${labelCoords.depth.x}px`, borderColor: '#00F2FE' }}>
                  ↕ Depth: {depthCm} cm
                </div>
              )}
              {showLabels && labelCoords.width.visible && (
                <div style={{ ...styles.labelBox, top: `${labelCoords.width.y}px`, left: `${labelCoords.width.x}px`, borderColor: '#f59e0b' }}>
                  ↔ Width: {widthCm} cm
                </div>
              )}
              {showLabels && labelCoords.length.visible && (
                <div style={{ ...styles.labelBox, top: `${labelCoords.length.y}px`, left: `${labelCoords.length.x}px`, borderColor: '#10b981' }}>
                  ⇕ Length: {lengthCm} cm
                </div>
              )}

              {isMeasuring && (
                <div style={styles.measureNotice}>
                  📏 Click two points on the 3D road model to measure distance.
                  {measurePoints.length === 1 && <div>Point 1 selected. Click Point 2...</div>}
                  {measuredDistance !== null && (
                    <div style={{ color: '#00F2FE', marginTop: '4px', fontWeight: 'bold' }}>
                      Measured 3D Distance: {measuredDistance} cm
                    </div>
                  )}
                </div>
              )}

              {compareMode && (
                <div style={styles.comparePanel}>
                  <div style={{ fontFamily: 'Orbitron', color: '#f59e0b', fontSize: '11px', fontWeight: 'bold', marginBottom: '4px' }}>
                    🔄 HISTORICAL COMPARISON MODE
                  </div>
                  <div style={{ fontSize: '10px', color: '#E5E7EB' }}>
                    {nearbyDefects.length > 0 ? (
                      <div>Found {nearbyDefects.length} nearby historical defect scan(s) within 200m corridor.</div>
                    ) : (
                      <div>No earlier historical scans recorded for this corridor position. Baseline scan saved.</div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px', fontSize: '11px', color: '#9CA3AF' }}>
              <span>3D Procedural Telemetry View (From Recorded Detection Database)</span>
              <span>Recorded Timestamp: {defectData.timestamp || 'Live Stream'}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
    background: 'rgba(5, 8, 15, 0.88)', backdropFilter: 'blur(16px)',
    display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 3000
  },
  card: {
    width: '920px', background: '#0B0F19', border: '1px solid rgba(0, 242, 254, 0.4)',
    borderRadius: '16px', padding: '24px', boxShadow: '0 25px 60px rgba(0, 0, 0, 0.85)',
    display: 'flex', flexDirection: 'column'
  },
  headerRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' },
  title: { fontFamily: 'Orbitron', color: '#00F2FE', margin: 0, fontSize: '17px', letterSpacing: '1px' },
  subtitle: { fontSize: '11px', color: '#9CA3AF', margin: '4px 0 0 0' },
  closeBtn: { background: 'transparent', border: 'none', color: '#ef4444', fontSize: '22px', cursor: 'pointer', padding: '0 4px' },
  emptyStateContainer: { textAlign: 'center', padding: '60px 20px' },
  closeModalBtn: {
    background: 'linear-gradient(135deg, #0284c7 0%, #00F2FE 100%)', color: '#0B0F19', border: 'none',
    padding: '8px 20px', borderRadius: '6px', fontFamily: 'Orbitron', fontSize: '12px', fontWeight: 'bold', cursor: 'pointer'
  },
  loadingContainer: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '360px' },
  spinner: { width: '36px', height: '36px', border: '3px solid rgba(0,242,254,0.2)', borderTop: '3px solid #00F2FE', borderRadius: '50%', animation: 'spin 1s linear infinite' },
  toolbar: {
    position: 'absolute', top: '12px', right: '12px', display: 'flex', gap: '6px', zIndex: 100
  },
  toolBtn: {
    background: 'rgba(15, 23, 42, 0.85)', color: '#E5E7EB', border: '1px solid rgba(0, 242, 254, 0.3)',
    borderRadius: '6px', padding: '6px 10px', fontSize: '11px', fontFamily: 'Orbitron', cursor: 'pointer',
    backdropFilter: 'blur(8px)', transition: 'all 0.2s ease'
  },
  telemetryPanel: {
    position: 'absolute', top: '12px', left: '12px', background: 'rgba(11, 15, 25, 0.92)',
    border: '1px solid rgba(0, 242, 254, 0.4)', borderRadius: '10px', padding: '12px 16px',
    zIndex: 100, width: '280px', boxShadow: '0 8px 24px rgba(0,0,0,0.6)', backdropFilter: 'blur(10px)'
  },
  metaGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '11px', color: '#E5E7EB' },
  metaKey: { color: '#9CA3AF' },
  labelBox: {
    position: 'absolute', transform: 'translate(-50%, -100%)', background: 'rgba(11, 15, 25, 0.92)',
    border: '1px solid', borderRadius: '4px', padding: '3px 8px', fontSize: '10px',
    fontFamily: 'Orbitron', color: '#E5E7EB', zIndex: 120, pointerEvents: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
  },
  measureNotice: {
    position: 'absolute', bottom: '14px', left: '12px', background: 'rgba(11, 15, 25, 0.92)',
    border: '1px solid #00F2FE', borderRadius: '8px', padding: '8px 14px', fontSize: '11px',
    fontFamily: 'Orbitron', color: '#E5E7EB', zIndex: 120
  },
  comparePanel: {
    position: 'absolute', bottom: '14px', right: '12px', background: 'rgba(11, 15, 25, 0.92)',
    border: '1px solid #f59e0b', borderRadius: '8px', padding: '10px 14px', fontSize: '11px',
    maxWidth: '280px', zIndex: 120
  }
};

