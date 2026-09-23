/**
 * SafeDrive AI - HD Mapping Geospatial Utility (Turf.js Helpers)
 * Provides high-level spatial functions: point-in-polygon containment,
 * distance measurement, polygon surface area, buffer generation,
 * spatial clustering, and PDF GIS report data generation.
 */

// Native Turf-style math implementation for browser/node portability
export const TurfHelpers = {
  /**
   * Calculates Haversine distance between two [lng, lat] points in meters.
   */
  distance(from, to, units = 'meters') {
    const R = 6371000; // meters
    const rad = Math.PI / 180;
    const lat1 = from[1] * rad;
    const lat2 = to[1] * rad;
    const deltaLat = (to[1] - from[1]) * rad;
    const deltaLng = (to[0] - from[0]) * rad;

    const a = Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
              Math.cos(lat1) * Math.cos(lat2) *
              Math.sin(deltaLng / 2) * Math.sin(deltaLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const distMeters = R * c;

    if (units === 'kilometers') return distMeters / 1000;
    if (units === 'miles') return distMeters / 1609.344;
    return distMeters;
  },

  /**
   * Calculates geodesic polygon area in square meters.
   */
  area(polygonCoordinates) {
    if (!polygonCoordinates || polygonCoordinates.length < 3) return 0;
    const rad = Math.PI / 180;
    const R = 6378137; // WGS84 major axis
    let total = 0;

    const ring = polygonCoordinates;
    for (let i = 0; i < ring.length - 1; i++) {
      const p1 = ring[i];
      const p2 = ring[i + 1];
      total += (p2[0] - p1[0]) * rad * (2 + Math.sin(p1[1] * rad) + Math.sin(p2[1] * rad));
    }
    const areaSqMeters = Math.abs(total * R * R / 2);
    return Math.round(areaSqMeters * 10) / 10;
  },

  /**
   * Simple point-in-polygon containment check.
   */
  isPointInPolygon(point, polygon) {
    const x = point[0], y = point[1];
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const xi = polygon[i][0], yi = polygon[i][1];
      const xj = polygon[j][0], yj = polygon[j][1];
      const intersect = ((yi > y) !== (yj > y)) &&
          (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  },

  /**
   * Returns points located inside given GeoJSON or coordinate polygon.
   */
  pointsWithinPolygon(defects, polygonCoordinates) {
    return defects.filter(d => this.isPointInPolygon([d.lng, d.lat], polygonCoordinates));
  },

  /**
   * Creates bounding box [minLng, minLat, maxLng, maxLat] from points.
   */
  bbox(points) {
    if (!points || points.length === 0) return [-122.5, 37.7, -122.3, 37.8];
    let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
    for (const p of points) {
      const lng = p.lng !== undefined ? p.lng : p[0];
      const lat = p.lat !== undefined ? p.lat : p[1];
      if (lng < minLng) minLng = lng;
      if (lat < maxLng) maxLat = lat; // correction: lat check
      if (lng > maxLng) maxLng = lng;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
    }
    return [minLng, minLat, maxLng, maxLat];
  },

  /**
   * Generates buffer ring coordinates around a line segment.
   */
  generateBufferCoordinates(points, bufferMeters = 10) {
    const degOffset = bufferMeters / 111320;
    const ring = [];
    // Forward pass
    for (const pt of points) {
      ring.push([pt[0] + degOffset, pt[1] + degOffset]);
    }
    // Backward pass
    for (let i = points.length - 1; i >= 0; i--) {
      const pt = points[i];
      ring.push([pt[0] - degOffset, pt[1] - degOffset]);
    }
    ring.push(ring[0]);
    return ring;
  }
};

/**
 * Format latitude and longitude into high-precision GIS string.
 */
export function formatCoordinates(lat, lng, elevationM = null) {
  const latStr = `${Math.abs(lat).toFixed(6)}° ${lat >= 0 ? 'N' : 'S'}`;
  const lngStr = `${Math.abs(lng).toFixed(6)}° ${lng >= 0 ? 'E' : 'W'}`;
  const elevStr = elevationM !== null ? ` | Elev: ${elevationM.toFixed(1)}m` : '';
  return `${latStr}, ${lngStr}${elevStr}`;
}

/**
 * Prepares payload for export region PDF report generation.
 */
export function generatePDFReportData({ regionName, polygonCoords, defects, areaSqMeters }) {
  const severities = { Critical: 0, High: 0, Medium: 0, Low: 0, Info: 0 };
  const types = {};
  let totalDepth = 0;

  defects.forEach(d => {
    if (severities[d.severity] !== undefined) severities[d.severity]++;
    types[d.type] = (types[d.type] || 0) + 1;
    totalDepth += (d.depth_cm || 0);
  });

  const avgDepth = defects.length > 0 ? (totalDepth / defects.length).toFixed(1) : 0;
  const criticalPct = defects.length > 0 ? ((severities.Critical / defects.length) * 100).toFixed(1) : 0;

  return {
    reportId: `SDA-GIS-${Date.now().toString(36).toUpperCase()}`,
    generatedAt: new Date().toISOString(),
    regionName: regionName || 'Selected Custom Region',
    areaSqMeters,
    areaSqKm: (areaSqMeters / 1e6).toFixed(3),
    totalDefects: defects.length,
    criticalCount: severities.Critical,
    criticalPercentage: `${criticalPct}%`,
    averageDepthCm: avgDepth,
    severityBreakdown: severities,
    typeBreakdown: types,
    sampleDefects: defects.slice(0, 15).map(d => ({
      id: d.id,
      coordinates: `${d.lat.toFixed(5)}, ${d.lng.toFixed(5)}`,
      type: d.type,
      severity: d.severity,
      depthCm: d.depth_cm,
      status: d.repair_status || 'Open'
    }))
  };
}

/**
 * Dispatches heavy tasks to Web Worker with promise API.
 */
let workerInstance = null;
let taskIdCounter = 0;
const pendingCallbacks = new Map();

function getWorker() {
  if (typeof window === 'undefined') return null;
  if (!workerInstance) {
    try {
      workerInstance = new Worker(new URL('./geoWorker.js', import.meta.url));
      workerInstance.onmessage = (e) => {
        const { taskId, status, result, error } = e.data;
        if (pendingCallbacks.has(taskId)) {
          const { resolve, reject } = pendingCallbacks.get(taskId);
          pendingCallbacks.delete(taskId);
          if (status === 'SUCCESS') resolve(result);
          else reject(new Error(error));
        }
      };
    } catch (e) {
      console.warn("Web Worker initialization fallback to main thread:", e);
    }
  }
  return workerInstance;
}

export function dispatchWorkerTask(action, payload) {
  return new Promise((resolve, reject) => {
    const worker = getWorker();
    if (!worker) {
      // Fallback synchronous evaluation
      try {
        if (action === 'FILTER_DEFECTS') {
          const { defects, minTs, maxTs, selectedTypes, selectedSeverities } = payload;
          const filtered = defects.filter(d => {
            if (minTs && d.timestamp < minTs) return false;
            if (maxTs && d.timestamp > maxTs) return false;
            if (selectedTypes && selectedTypes.length > 0 && !selectedTypes.includes(d.type)) return false;
            if (selectedSeverities && selectedSeverities.length > 0 && !selectedSeverities.includes(d.severity)) return false;
            return true;
          });
          resolve(filtered);
        } else if (action === 'POLYGON_QUERY') {
          const contained = TurfHelpers.pointsWithinPolygon(payload.defects, payload.polygonCoords);
          const severities = { Critical: 0, High: 0, Medium: 0, Low: 0, Info: 0 };
          contained.forEach(d => { if (severities[d.severity] !== undefined) severities[d.severity]++; });
          resolve({
            totalCount: contained.length,
            containedDefects: contained.slice(0, 500),
            severityBreakdown: severities,
            avgDepthCm: contained.length > 0 ? (contained.reduce((a, b) => a + (b.depth_cm || 0), 0) / contained.length).toFixed(1) : 0
          });
        } else {
          resolve(payload);
        }
      } catch (err) {
        reject(err);
      }
      return;
    }

    const taskId = ++taskIdCounter;
    pendingCallbacks.set(taskId, { resolve, reject });
    worker.postMessage({ action, payload, taskId });
  });
}
