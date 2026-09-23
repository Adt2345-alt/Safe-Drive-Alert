/**
 * SafeDrive AI - HD Mapping Web Worker
 * Offloads heavy spatial filtering, 100K+ marker processing, point-in-polygon containment,
 * and distance calculations off the main UI thread.
 */

// Simple Ray-Casting Point-in-Polygon check inside worker
function isPointInPolygon(point, polygon) {
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
}

// Haversine formula for exact distance between two coordinates in meters
function haversineDistance(coords1, coords2) {
  const R = 6371000; // Radius of Earth in meters
  const lat1 = coords1[1] * Math.PI / 180;
  const lat2 = coords2[1] * Math.PI / 180;
  const deltaLat = (coords2[1] - coords1[1]) * Math.PI / 180;
  const deltaLng = (coords2[0] - coords1[0]) * Math.PI / 180;

  const a = Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
            Math.cos(lat1) * Math.cos(lat2) *
            Math.sin(deltaLng / 2) * Math.sin(deltaLng / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

self.onmessage = function (e) {
  const { action, payload, taskId } = e.data;

  try {
    if (action === 'FILTER_DEFECTS') {
      const { defects, minTs, maxTs, selectedTypes, selectedSeverities } = payload;
      const filtered = [];

      for (let i = 0; i < defects.length; i++) {
        const d = defects[i];
        if (minTs && d.timestamp < minTs) continue;
        if (maxTs && d.timestamp > maxTs) continue;
        if (selectedTypes && selectedTypes.length > 0 && !selectedTypes.includes(d.type)) continue;
        if (selectedSeverities && selectedSeverities.length > 0 && !selectedSeverities.includes(d.severity)) continue;
        filtered.push(d);
      }

      self.postMessage({ taskId, status: 'SUCCESS', result: filtered });
    } 
    else if (action === 'POLYGON_QUERY') {
      const { defects, polygonCoords } = payload;
      const contained = [];
      const severityBreakdown = { Critical: 0, High: 0, Medium: 0, Low: 0, Info: 0 };
      const typeBreakdown = {};

      for (let i = 0; i < defects.length; i++) {
        const d = defects[i];
        if (isPointInPolygon([d.lng, d.lat], polygonCoords)) {
          contained.push(d);
          if (severityBreakdown[d.severity] !== undefined) {
            severityBreakdown[d.severity]++;
          }
          typeBreakdown[d.type] = (typeBreakdown[d.type] || 0) + 1;
        }
      }

      const totalDepth = contained.reduce((acc, curr) => acc + (curr.depth_cm || 0), 0);
      const avgDepthCm = contained.length > 0 ? (totalDepth / contained.length).toFixed(1) : 0;

      self.postMessage({
        taskId,
        status: 'SUCCESS',
        result: {
          totalCount: contained.length,
          containedDefects: contained.slice(0, 500),
          severityBreakdown,
          typeBreakdown,
          avgDepthCm
        }
      });
    }
    else if (action === 'MEASURE_DISTANCE') {
      const { points } = payload; // Array of [lng, lat]
      let totalMeters = 0;
      const segments = [];

      for (let i = 0; i < points.length - 1; i++) {
        const dist = haversineDistance(points[i], points[i + 1]);
        totalMeters += dist;
        segments.push({
          from: points[i],
          to: points[i + 1],
          distanceMeters: Math.round(dist * 10) / 10
        });
      }

      self.postMessage({
        taskId,
        status: 'SUCCESS',
        result: {
          totalMeters: Math.round(totalMeters * 10) / 10,
          totalKm: Math.round((totalMeters / 1000) * 100) / 100,
          segments
        }
      });
    }
    else {
      self.postMessage({ taskId, status: 'ERROR', error: 'Unknown action type' });
    }
  } catch (err) {
    self.postMessage({ taskId, status: 'ERROR', error: err.message });
  }
};
