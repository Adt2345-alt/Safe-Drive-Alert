"""
SafeDrive AI - Defects Database Access Layer
Manages data/defects.db SQLite storage for real detections from Simulation Drive
and Road Video Analyzer uploads.
"""

import sqlite3
import os
import time
import random
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("SafeDrive.DefectsDB")
logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DEFECTS_DB_PATH = os.path.join(DATA_DIR, 'defects.db')

BANGALORE_ROADS = {
    "MG Road": ((12.9715, 77.6010), (12.9755, 77.6200)),
    "Old Airport Road": ((12.9620, 77.6300), (12.9560, 77.6650)),
    "Koramangala 80ft Road": ((12.9420, 77.6210), (12.9280, 77.6270)),
    "Indiranagar 100ft Road": ((12.9650, 77.6410), (12.9910, 77.6390)),
    "Hebbal Flyover": ((13.0300, 77.5950), (13.0420, 77.5990)),
    "Silk Board Junction": ((12.9150, 77.6210), (12.9200, 77.6260)),
    "Malleshwaram 8th Cross": ((12.9980, 77.5670), (13.0070, 77.5730)),
    "Jayanagar 4th Block": ((12.9240, 77.5800), (12.9340, 77.5850)),
    "Whitefield Main Road": ((12.9620, 77.7350), (12.9750, 77.7600)),
    "HSR Layout Sector 2": ((12.9080, 77.6380), (12.9150, 77.6520)),
    "Rajajinagar 1st Block": ((12.9930, 77.5520), (13.0030, 77.5580)),
    "Basavanagudi Bull Temple Rd": ((12.9380, 77.5650), (12.9480, 77.5710)),
    "Yelahanka Main Road": ((13.0900, 77.5920), (13.1100, 77.6000)),
    "Marathahalli Bridge": ((12.9510, 77.6950), (12.9590, 77.7080)),
    "Domlur Layout": ((12.9570, 77.6320), (12.9650, 77.6430)),
}

def get_db_connection():
    conn = sqlite3.connect(DEFECTS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_defects_db():
    """Initializes SQLite schema for real defect detections."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS defects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp INTEGER NOT NULL,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        defect_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0.90,
        depth_cm REAL NOT NULL DEFAULT 5.0,
        width_cm REAL NOT NULL DEFAULT 30.0,
        length_cm REAL NOT NULL DEFAULT 40.0,
        road_name TEXT,
        city TEXT DEFAULT 'Bengaluru',
        detection_source TEXT DEFAULT 'Simulation Drive',
        repair_status TEXT DEFAULT 'Pending',
        image_path TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicles (
        id TEXT PRIMARY KEY,
        driver_name TEXT NOT NULL,
        model TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        last_ping INTEGER NOT NULL,
        defects_detected INTEGER NOT NULL DEFAULT 0,
        current_lat REAL,
        current_lng REAL,
        current_road TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id TEXT NOT NULL,
        road_name TEXT,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        timestamp INTEGER NOT NULL,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
    )
    """)

    # Ensure missing columns exist for older DB files
    cols = [col[1] for col in cursor.execute("PRAGMA table_info(defects)").fetchall()]
    if "lat" not in cols:
        cursor.execute("ALTER TABLE defects ADD COLUMN lat REAL")
    if "lng" not in cols:
        cursor.execute("ALTER TABLE defects ADD COLUMN lng REAL")
    if "width_cm" not in cols:
        cursor.execute("ALTER TABLE defects ADD COLUMN width_cm REAL")
    if "length_cm" not in cols:
        cursor.execute("ALTER TABLE defects ADD COLUMN length_cm REAL")
    if "repair_status" not in cols:
        cursor.execute("ALTER TABLE defects ADD COLUMN repair_status TEXT DEFAULT 'Pending'")
    if "vehicle_id" not in cols:
        cursor.execute("ALTER TABLE defects ADD COLUMN vehicle_id TEXT")

    conn.commit()
    conn.close()

def generate_defect_data(
    road_name: Optional[str] = None,
    depth_cm: Optional[float] = None,
    width_cm: Optional[float] = None,
    length_cm: Optional[float] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    confidence: Optional[float] = None,
    defect_type: Optional[str] = None,
    timestamp: Optional[int] = None,
    repair_status: Optional[str] = None,
    severity: Optional[str] = None
) -> Dict[str, Any]:
    if road_name is None or road_name not in BANGALORE_ROADS:
        road_name = random.choice(list(BANGALORE_ROADS.keys()))
    
    if lat is None or lng is None:
        (start_lat, start_lng), (end_lat, end_lng) = BANGALORE_ROADS[road_name]
        t = random.uniform(0.0, 1.0)
        base_lat = start_lat + t * (end_lat - start_lat)
        base_lng = start_lng + t * (end_lng - start_lng)
        # ±30m jitter (~0.00027 deg lat, ~0.00028 deg lng)
        jitter_lat = random.uniform(-30, 30) / 111000.0
        jitter_lng = random.uniform(-30, 30) / 108000.0
        lat = round(base_lat + jitter_lat, 6)
        lng = round(base_lng + jitter_lng, 6)
    
    if depth_cm is None:
        depth_cm = round(random.uniform(2.0, 25.0), 1)
    if width_cm is None:
        width_cm = round(random.uniform(15.0, 80.0), 1)
    if length_cm is None:
        length_cm = round(random.uniform(20.0, 120.0), 1)
        
    if severity is None:
        # derive severity from depth_cm: <5 Low, <10 Medium, <18 High, >=18 Critical
        if depth_cm < 5.0:
            severity = "Low"
        elif depth_cm < 10.0:
            severity = "Medium"
        elif depth_cm < 18.0:
            severity = "High"
        else:
            severity = "Critical"

    if confidence is None:
        confidence = round(random.uniform(0.65, 0.98), 2)
        
    if repair_status is None:
        if severity == "Low":
            repair_status = "Repaired" if random.random() < 0.60 else "Pending"
        else:
            repair_status = "Pending"

    if defect_type is None:
        defect_type = random.choice(["pothole", "pothole", "crack", "speedbump"])

    if timestamp is None:
        timestamp = int(time.time())

    return {
        "timestamp": timestamp,
        "lat": lat,
        "lng": lng,
        "latitude": lat,
        "longitude": lng,
        "defect_type": defect_type,
        "severity": severity,
        "confidence": confidence,
        "depth_cm": depth_cm,
        "width_cm": width_cm,
        "length_cm": length_cm,
        "road_name": road_name,
        "city": "Bengaluru",
        "detection_source": "Simulation Drive",
        "repair_status": repair_status
    }

def insert_defect(
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    defect_type: Optional[str] = None,
    severity: Optional[str] = None,
    confidence: Optional[float] = None,
    depth_cm: Optional[float] = None,
    width_cm: Optional[float] = None,
    length_cm: Optional[float] = None,
    road_name: Optional[str] = None,
    city: str = "Bengaluru",
    detection_source: str = "Simulation Drive",
    repair_status: Optional[str] = None,
    timestamp: Optional[int] = None,
    image_path: str = None,
    notes: str = None
) -> int:

    """Inserts a real detection into SQLite defects.db using realistic attribute rules."""
    final_lat = lat if lat is not None else latitude
    final_lng = lng if lng is not None else longitude

    data = generate_defect_data(
        road_name=road_name,
        depth_cm=depth_cm,
        width_cm=width_cm,
        length_cm=length_cm,
        lat=final_lat,
        lng=final_lng,
        confidence=confidence,
        defect_type=defect_type,
        timestamp=timestamp,
        repair_status=repair_status,
        severity=severity
    )

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO defects (timestamp, lat, lng, latitude, longitude, defect_type, severity, confidence, depth_cm, width_cm, length_cm, road_name, city, detection_source, repair_status, image_path, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["timestamp"], data["lat"], data["lng"], data["latitude"], data["longitude"],
        data["defect_type"], data["severity"], data["confidence"], data["depth_cm"],
        data["width_cm"], data["length_cm"], data["road_name"], data["city"],
        detection_source, data["repair_status"], image_path, notes
    ))
    
    inserted_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return inserted_id

def query_defects(
    min_ts: Optional[int] = None,
    max_ts: Optional[int] = None,
    severity: Optional[str] = None,
    defect_type: Optional[str] = None,
    bbox: Optional[List[float]] = None,
    limit: int = 10000
) -> List[Dict[str, Any]]:
    """Queries SQLite defects.db for real recorded detections."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM defects WHERE 1=1"
    params = []

    if min_ts:
        query += " AND timestamp >= ?"
        params.append(min_ts)
    if max_ts:
        query += " AND timestamp <= ?"
        params.append(max_ts)
    if severity and severity != "ALL":
        query += " AND severity = ?"
        params.append(severity)
    if defect_type and defect_type != "ALL":
        query += " AND defect_type = ?"
        params.append(defect_type)
    if bbox and len(bbox) == 4:
        min_lng, min_lat, max_lng, max_lat = bbox
        query += " AND (lng >= ? OR longitude >= ?) AND (lng <= ? OR longitude <= ?) AND (lat >= ? OR latitude >= ?) AND (lat <= ? OR latitude <= ?)"
        params.extend([min_lng, min_lng, max_lng, max_lng, min_lat, min_lat, max_lat, max_lat])

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = cursor.execute(query, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        d_lat = float(d["lat"]) if d.get("lat") is not None else float(d["latitude"])
        d_lng = float(d["lng"]) if d.get("lng") is not None else float(d["longitude"])
        depth = float(d["depth_cm"])
        width = float(d["width_cm"]) if d.get("width_cm") is not None else round(depth * 6.0, 1)
        length = float(d["length_cm"]) if d.get("length_cm") is not None else round(depth * 8.0, 1)
        result.append({
            "id": f"DEF-{d['id']:05d}",
            "raw_id": d["id"],
            "timestamp": d["timestamp"],
            "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(d["timestamp"])),
            "lat": d_lat,
            "lng": d_lng,
            "type": d["defect_type"],
            "severity": d["severity"],
            "confidence": float(d["confidence"]),
            "depth_cm": depth,
            "width_cm": width,
            "length_cm": length,
            "corridor": d["road_name"] or "Recorded Route",
            "road_name": d["road_name"] or "Recorded Route",
            "city": d["city"] or "Bengaluru",
            "detected_by_vehicle": d.get("vehicle_id") or d["detection_source"],
            "vehicle_id": d.get("vehicle_id"),
            "repair_status": d.get("repair_status", "Pending")
        })

    return result

def get_defect_by_id(defect_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single defect by integer ID from defects.db."""
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM defects WHERE id = ?", (defect_id,)).fetchone()
    conn.close()

    if not row:
        return None

    d = dict(row)
    d_lat = float(d["lat"]) if d.get("lat") is not None else float(d["latitude"])
    d_lng = float(d["lng"]) if d.get("lng") is not None else float(d["longitude"])
    depth = float(d["depth_cm"])
    width = float(d["width_cm"]) if d.get("width_cm") is not None else round(depth * 6.0, 1)
    length = float(d["length_cm"]) if d.get("length_cm") is not None else round(depth * 8.0, 1)

    return {
        "id": d["id"],
        "formatted_id": f"DEF-{d['id']:05d}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(d["timestamp"])),
        "epoch_timestamp": d["timestamp"],
        "lat": d_lat,
        "lng": d_lng,
        "type": d["defect_type"],
        "severity": d["severity"],
        "confidence": round(float(d.get("confidence", 0.90)), 2),
        "depth_cm": depth,
        "width_cm": width,
        "length_cm": length,
        "road_name": d["road_name"] or "MG Road Corridor",
        "city": d["city"] or "Bengaluru",
        "source": d["detection_source"] or "Simulation Drive",
        "vehicle_id": d.get("vehicle_id"),
        "image_path": d.get("image_path"),
        "notes": d.get("notes"),
        "repair_status": d.get("repair_status", "Pending")
    }

def query_nearby_defects(lat: float, lng: float, radius_m: float = 100.0) -> List[Dict[str, Any]]:
    """Queries defects near a lat/lng position for comparison mode."""
    lat_delta = radius_m / 111000.0
    lng_delta = radius_m / 108000.0

    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT * FROM defects WHERE (lat BETWEEN ? AND ? OR latitude BETWEEN ? AND ?) AND (lng BETWEEN ? AND ? OR longitude BETWEEN ? AND ?)",
        (lat - lat_delta, lat + lat_delta, lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta, lng - lng_delta, lng + lng_delta)
    ).fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        d_lat = float(d["lat"]) if d.get("lat") is not None else float(d["latitude"])
        d_lng = float(d["lng"]) if d.get("lng") is not None else float(d["longitude"])
        depth = float(d["depth_cm"])
        results.append({
            "id": d["id"],
            "formatted_id": f"DEF-{d['id']:05d}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(d["timestamp"])),
            "lat": d_lat,
            "lng": d_lng,
            "type": d["defect_type"],
            "severity": d["severity"],
            "confidence": round(float(d.get("confidence", 0.90)), 2),
            "depth_cm": depth,
            "width_cm": float(d["width_cm"]) if d.get("width_cm") is not None else round(depth * 6.0, 1),
            "length_cm": float(d["length_cm"]) if d.get("length_cm") is not None else round(depth * 8.5, 1),
            "road_name": d["road_name"] or "MG Road Corridor",
            "source": d["detection_source"] or "Simulation Drive",
            "repair_status": d.get("repair_status", "Pending")
        })
    return results

def get_vehicles(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves vehicles from defects.db with status filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM vehicles WHERE 1=1"
    params = []
    if status and status.lower() != 'all':
        query += " AND LOWER(status) = ?"
        params.append(status.lower())
    query += " ORDER BY id ASC"
    rows = cursor.execute(query, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        v = dict(r)
        result.append({
            "id": v["id"],
            "driver_name": v["driver_name"],
            "model": v["model"],
            "status": v["status"],
            "last_ping": v["last_ping"],
            "last_ping_formatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(v["last_ping"])),
            "defects_detected": int(v.get("defects_detected", 0)),
            "current_lat": float(v["current_lat"]) if v.get("current_lat") is not None else 12.9716,
            "current_lng": float(v["current_lng"]) if v.get("current_lng") is not None else 77.5946,
            "current_road": v.get("current_road") or "MG Road"
        })
    return result

def get_vehicle_by_id(vehicle_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves vehicle detail including assigned defects and route telemetry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    v_row = cursor.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    if not v_row:
        conn.close()
        return None

    v = dict(v_row)
    
    # Query assigned defects
    d_rows = cursor.execute("SELECT * FROM defects WHERE vehicle_id = ? ORDER BY timestamp DESC", (vehicle_id,)).fetchall()
    defects = []
    for dr in d_rows:
        d = dict(dr)
        defects.append({
            "id": f"DEF-{d['id']:05d}",
            "raw_id": d["id"],
            "type": d["defect_type"],
            "severity": d["severity"],
            "lat": float(d["lat"]) if d.get("lat") is not None else float(d["latitude"]),
            "lng": float(d["lng"]) if d.get("lng") is not None else float(d["longitude"]),
            "depth_cm": float(d["depth_cm"]),
            "road_name": d.get("road_name") or "MG Road",
            "timestamp": d["timestamp"]
        })

    # Query route points
    r_rows = cursor.execute("SELECT * FROM vehicle_routes WHERE vehicle_id = ? ORDER BY timestamp ASC", (vehicle_id,)).fetchall()
    route = []
    for rr in r_rows:
        r = dict(rr)
        route.append({
            "id": r["id"],
            "road_name": r.get("road_name"),
            "lat": float(r["lat"]),
            "lng": float(r["lng"]),
            "timestamp": r["timestamp"]
        })

    conn.close()

    return {
        "id": v["id"],
        "driver_name": v["driver_name"],
        "model": v["model"],
        "status": v["status"],
        "last_ping": v["last_ping"],
        "last_ping_formatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(v["last_ping"])),
        "defects_detected": int(v.get("defects_detected", 0)),
        "current_lat": float(v["current_lat"]) if v.get("current_lat") is not None else 12.9716,
        "current_lng": float(v["current_lng"]) if v.get("current_lng") is not None else 77.5946,
        "current_road": v.get("current_road") or "MG Road",
        "defects": defects,
        "route": route
    }

def get_vehicle_routes(vehicle_id: Optional[str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
    """Retrieves route history points."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM vehicle_routes WHERE 1=1"
    params = []
    if vehicle_id:
        query += " AND vehicle_id = ?"
        params.append(vehicle_id)
    query += " ORDER BY timestamp ASC LIMIT ?"
    params.append(limit)
    rows = cursor.execute(query, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        rr = dict(r)
        result.append({
            "id": rr["id"],
            "vehicle_id": rr["vehicle_id"],
            "road_name": rr.get("road_name"),
            "lat": float(rr["lat"]),
            "lng": float(rr["lng"]),
            "timestamp": rr["timestamp"]
        })
    return result

def get_fleet_coverage(days: int = 7) -> Dict[str, Any]:
    """Calculates road network coverage for specified days."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = int(time.time())
    
    corridors = list(BANGALORE_ROADS.keys())
    coverage_details = []
    covered_count = 0

    for road in corridors:
        r_row = cursor.execute("SELECT MAX(timestamp) FROM vehicle_routes WHERE road_name = ?", (road,)).fetchone()
        d_row = cursor.execute("SELECT MAX(timestamp) FROM defects WHERE road_name = ?", (road,)).fetchone()
        
        r_ts = r_row[0] if r_row and r_row[0] else 0
        d_ts = d_row[0] if d_row and d_row[0] else 0
        max_ts = max(r_ts, d_ts)

        age_days = round((now - max_ts) / 86400.0, 1) if max_ts > 0 else 999.0
        
        if age_days <= 7:
            status = "green"
        elif age_days <= 30:
            status = "yellow"
        else:
            status = "red"

        if age_days <= days:
            covered_count += 1

        (start_lat, start_lng), (end_lat, end_lng) = BANGALORE_ROADS[road]
        coverage_details.append({
            "road_name": road,
            "start_coords": [start_lat, start_lng],
            "end_coords": [end_lat, end_lng],
            "last_scanned_timestamp": max_ts,
            "last_scanned_formatted": time.strftime("%Y-%m-%d %H:%M", time.localtime(max_ts)) if max_ts > 0 else "Never",
            "age_days": age_days,
            "status": status
        })

    conn.close()

    total_roads = len(corridors)
    pct_covered = round((covered_count / total_roads) * 100.0, 1) if total_roads > 0 else 0.0

    return {
        "status": "success",
        "days": days,
        "total_corridors": total_roads,
        "covered_corridors": covered_count,
        "coverage_percentage": pct_covered,
        "corridors": coverage_details
    }

# Initialize schema on import
init_defects_db()


