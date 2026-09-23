"""
SafeDrive AI - Defects Database Access Layer
Manages data/defects.db SQLite storage for real detections from Simulation Drive
and Road Video Analyzer uploads.
"""

import sqlite3
import os
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("SafeDrive.DefectsDB")
logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DEFECTS_DB_PATH = os.path.join(DATA_DIR, 'defects.db')

def get_db_connection():
    conn = sqlite3.connect(DEFECTS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_defects_db():
    """Initializes SQLite schema for real defect detections and seeds realistic examples if empty."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS defects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp INTEGER NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        defect_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0.90,
        depth_cm REAL NOT NULL DEFAULT 5.0,
        road_name TEXT,
        city TEXT DEFAULT 'Bengaluru',
        detection_source TEXT DEFAULT 'Simulation Drive',
        image_path TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()
    seed_realistic_defects()

def seed_realistic_defects():
    """Seeds realistic example defects in Bengaluru, India if the table is empty or has no India points."""
    conn = get_db_connection()
    cursor = conn.cursor()
    count = cursor.execute("SELECT COUNT(*) FROM defects WHERE latitude BETWEEN 8.0 AND 30.0").fetchone()[0]
    conn.close()

    if count > 0:
        return

    sample_defects = [
        {"lat": 12.9725, "lng": 77.6180, "type": "pothole", "sev": "Critical", "conf": 0.96, "depth": 9.8, "road": "MG Road (Near Trinity Metro)"},
        {"lat": 12.9710, "lng": 77.6070, "type": "pothole", "sev": "High", "conf": 0.93, "depth": 7.5, "road": "Brigade Road Junction"},
        {"lat": 12.9740, "lng": 77.6120, "type": "pothole", "sev": "Medium", "conf": 0.89, "depth": 6.2, "road": "Mayo Hall Circle"},
        {"lat": 12.9760, "lng": 77.6010, "type": "speedbump", "sev": "High", "conf": 0.94, "depth": 5.5, "road": "Anil Kumble Circle"},
        {"lat": 12.9785, "lng": 77.6410, "type": "pothole", "sev": "Critical", "conf": 0.97, "depth": 11.4, "road": "Indiranagar 100ft Road (12th Main)"},
        {"lat": 12.9792, "lng": 77.6435, "type": "pothole", "sev": "High", "conf": 0.91, "depth": 8.2, "road": "Indiranagar (Toit Corridor)"},
        {"lat": 12.9768, "lng": 77.6380, "type": "crack", "sev": "Low", "conf": 0.86, "depth": 3.5, "road": "Indiranagar 6th Main"},
        {"lat": 12.9352, "lng": 77.6245, "type": "pothole", "sev": "High", "conf": 0.95, "depth": 8.8, "road": "Koramangala 80ft Road (Sony World Signal)"},
        {"lat": 12.9340, "lng": 77.6210, "type": "speedbump", "sev": "Medium", "conf": 0.90, "depth": 6.0, "road": "Koramangala 5th Block Corridor"},
        {"lat": 12.9365, "lng": 77.6160, "type": "crack", "sev": "Medium", "conf": 0.88, "depth": 4.1, "road": "Forum Mall Underpass (Koramangala)"},
        {"lat": 12.9280, "lng": 77.6850, "type": "pothole", "sev": "Critical", "conf": 0.98, "depth": 10.8, "road": "Outer Ring Road (Ecoworld Flyover)"},
        {"lat": 12.9550, "lng": 77.6980, "type": "pothole", "sev": "High", "conf": 0.92, "depth": 7.9, "road": "Marathahalli Bridge Corridor"},
        {"lat": 12.9240, "lng": 77.6520, "type": "crack", "sev": "Low", "conf": 0.85, "depth": 4.5, "road": "Sarjapur Road Junction"},
        {"lat": 13.0355, "lng": 77.5975, "type": "pothole", "sev": "Critical", "conf": 0.95, "depth": 9.1, "road": "Hebbal Flyover Heavy Corridor"},
        {"lat": 13.0120, "lng": 77.5840, "type": "speedbump", "sev": "Medium", "conf": 0.91, "depth": 5.8, "road": "Mekhri Circle Approach"}
    ]

    for item in sample_defects:
        insert_defect(
            latitude=item["lat"],
            longitude=item["lng"],
            defect_type=item["type"],
            severity=item["sev"],
            confidence=item["conf"],
            depth_cm=item["depth"],
            road_name=item["road"],
            city="Bengaluru",
            detection_source="SafeDrive Telemetry"
        )


def insert_defect(
    latitude: float,
    longitude: float,
    defect_type: str,
    severity: str,
    confidence: float = 0.90,
    depth_cm: float = 5.0,
    road_name: str = "MG Road Corridor",
    city: str = "Bengaluru",
    detection_source: str = "Simulation Drive",
    image_path: str = None,
    notes: str = None
) -> int:

    """Inserts a real detection into SQLite defects.db."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    ts = int(time.time())
    cursor.execute("""
    INSERT INTO defects (timestamp, latitude, longitude, defect_type, severity, confidence, depth_cm, road_name, city, detection_source, image_path, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ts, round(latitude, 6), round(longitude, 6), defect_type, severity,
        confidence, depth_cm, road_name, city, detection_source, image_path, notes
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
        query += " AND longitude >= ? AND longitude <= ? AND latitude >= ? AND latitude <= ?"
        params.extend([min_lng, max_lng, min_lat, max_lat])

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = cursor.execute(query, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        result.append({
            "id": f"DEF-{d['id']:05d}",
            "raw_id": d["id"],
            "timestamp": d["timestamp"],
            "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(d["timestamp"])),
            "lat": d["latitude"],
            "lng": d["longitude"],
            "type": d["defect_type"],
            "severity": d["severity"],
            "confidence": d["confidence"],
            "depth_cm": d["depth_cm"],
            "width_cm": round(d["depth_cm"] * 6.0, 1),
            "length_cm": round(d["depth_cm"] * 8.5, 1),
            "corridor": d["road_name"] or "Recorded Route",
            "city": d["city"],
            "detected_by_vehicle": d["detection_source"],
            "repair_status": "Open"
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
    depth = float(d["depth_cm"])
    width = round(depth * 6.0, 1)
    length = round(depth * 8.5, 1)

    return {
        "id": d["id"],
        "formatted_id": f"DEF-{d['id']:05d}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(d["timestamp"])),
        "epoch_timestamp": d["timestamp"],
        "lat": d["latitude"],
        "lng": d["longitude"],
        "type": d["defect_type"],
        "severity": d["severity"],
        "confidence": round(d.get("confidence", 0.90), 2),
        "depth_cm": depth,
        "width_cm": width,
        "length_cm": length,
        "road_name": d["road_name"] or "MG Road Corridor",
        "city": d["city"] or "Bengaluru",
        "source": d["detection_source"] or "Simulation Drive",

        "image_path": d.get("image_path"),
        "notes": d.get("notes"),
        "repair_status": "Open"
    }

def query_nearby_defects(lat: float, lng: float, radius_m: float = 100.0) -> List[Dict[str, Any]]:
    """Queries defects near a lat/lng position for comparison mode."""
    lat_delta = radius_m / 111000.0
    lng_delta = radius_m / 85000.0

    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT * FROM defects WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?",
        (lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta)
    ).fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        depth = float(d["depth_cm"])
        results.append({
            "id": d["id"],
            "formatted_id": f"DEF-{d['id']:05d}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(d["timestamp"])),
            "lat": d["latitude"],
            "lng": d["longitude"],
            "type": d["defect_type"],
            "severity": d["severity"],
            "confidence": round(d.get("confidence", 0.90), 2),
            "depth_cm": depth,
            "width_cm": round(depth * 6.0, 1),
            "length_cm": round(depth * 8.5, 1),
            "road_name": d["road_name"] or "Golden Gate Park Route",
            "source": d["detection_source"] or "Simulation Drive"
        })
    return results

# Initialize schema on import
init_defects_db()

