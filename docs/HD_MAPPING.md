# HD Mapping & Digital Twin System Specification

## Overview

The **SafeDrive AI HD Mapping & Digital Twin System** is an enterprise geospatial visualization engine designed to render high-density road defect telemetry, 3D building extrusions, time-series defect degradation trends, animated vehicle trajectories, and 3D road segment digital twins.

---

## 1. System Architecture & Base Map Configuration

```
                                  +---------------------------------------+
                                  |         Web Browser Frontend          |
                                  | MapLibre GL JS + Deck.gl + Three.js   |
                                  +-------------------+-------------------+
                                                      |
                                     Async REST API / Vector Tiles
                                                      |
                                  +-------------------v-------------------+
                                  |       Flask HD Map Data API           |
                                  |       (backend/api/map_data.py)       |
                                  +---------+-------------------+---------+
                                            |                   |
                           Spatial Bounding Box / Cache         |
                                            |                   v
                               +------------v-----+    +--------+--------+
                               |   Redis Cache    |    |  Option A 3D    |
                               | (LRU Fallback)   |    | Digital Twin    |
                               +------------------+    +-----------------+
```

### Keyless Open Basemap Setup
- **Map Library**: MapLibre GL JS v3.6.2 (`maplibre-gl.js`, `maplibre-gl.css`)
- **Vector Basemap Style**: OpenFreeMap Dark (`https://tiles.openfreemap.org/styles/dark`)
- **Attribution**: `MAP DATA © OpenStreetMap contributors, © OpenFreeMap`

---

## 2. Standardized Color Palette & GIS Layers

### 2.1 Severity Colors
- **Critical**: `#ef4444` (Red) — Urgent hazard requiring immediate patching
- **High**: `#f59e0b` (Orange) — High degradation risk
- **Medium**: `#eab308` (Yellow) — Moderate surface wear
- **Low**: `#3b82f6` (Blue) — Minor surface crack or marking anomaly
- **Repaired**: `#10b981` (Green) — Municipal work order completed

### 2.2 Layer Controls (Right Sidebar)
- **Base Map**: CartoDB Dark Matter vector road network & building footprints
- **Defects**: Color-coded severity markers & 3D column extrusions
- **Heatmap**: GPU-accelerated spatial density aggregation
- **Trajectory**: Animated vehicle path trails
- **Predicted**: Degradation forecast rings (30/60/90 days)
- **Municipality**: GeoJSON work order repair zone polygons

---

## 3. Top KPI Summary Cards & Filter Bar

### 3.1 Dynamic KPI Summary Cards
Calculates real-time stats based on active filters and time scrubbing:
- `TOTAL`: Total active defects visible
- `CRITICAL`: Count of critical defects (`#ef4444`)
- `HIGH`: Count of high severity defects (`#f59e0b`)
- `MEDIUM`: Count of medium severity defects (`#eab308`)
- `LOW`: Count of low severity defects (`#3b82f6`)
- `REPAIRED`: Count of resolved municipal work orders (`#10b981`)

### 3.2 Filter Controls Bar
- `Severity`: Dropdown filter (`All`, `Critical`, `High`, `Medium`, `Low`)
- `Type`: Dropdown filter (`All`, `Pothole`, `Crack`, `Rutting`, `Marking Degradation`, `Speedbump`)
- `Date Range`: Dropdown filter (`All Time`, `Last 7 Days`, `Last 30 Days`, `Last 90 Days`)
- `Search`: Real-time text search by Defect ID or Street Corridor name

---

## 4. Option A: Digital Twin 3D Preview

The **Digital Twin Module** (`frontend/components/DigitalTwin.jsx`) presents a simplified 3D road segment preview:
- **Three.js WebGL Engine**: User interactive `OrbitControls` for smooth mouse rotation, pan, and zoom.
- **Textured Road Plane**: Asphalt surface representation with lane markings.
- **3D Defect Geometry**: Potholes rendered as 3D depth cylinders where cylinder height equals actual recorded depth ($cm$).
- **Surrounding Buildings**: 3D box geometries rendering nearby urban context.
- **Honest Pipeline Status**: Labeled as `"Simplified 3D Preview"` with status `"COLMAP reconstruction status: Standby / Preview Mode"`.

---

## 5. API Reference Guide

### `GET /api/map/defects`
Returns filtered defect points for Map View & Time Playback.
- **Parameters**: `min_ts`, `max_ts`, `severity`, `type`, `bbox`, `limit`.

### `GET /api/map/heatmap`
Returns aggregated spatial density data for GPU heatmaps.

### `GET /api/map/trajectory`
Returns animated vehicle path trajectory with timestamps.

### `GET /api/map/predictions`
Returns forecasted pothole degradation hotspots.

### `GET /api/map/municipality/work-orders`
Returns GeoJSON FeatureCollection of municipal work order zones.
