import os
import sys
import time
import random
import sqlite3

# Add workspace root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.api.defects_db import (
    get_db_connection,
    init_defects_db,
    insert_defect,
    BANGALORE_ROADS
)

def seed_defects(count=1200):
    print(f"Initializing database and seeding {count} realistic defects...")
    init_defects_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM defects;")
    conn.commit()
    conn.close()

    now = int(time.time())
    thirty_days_seconds = 30 * 86400

    roads_list = list(BANGALORE_ROADS.keys())

    for i in range(count):
        road_name = random.choice(roads_list)
        (start_lat, start_lng), (end_lat, end_lng) = BANGALORE_ROADS[road_name]
        t = random.uniform(0.0, 1.0)
        base_lat = start_lat + t * (end_lat - start_lat)
        base_lng = start_lng + t * (end_lng - start_lng)
        
        # ±30m jitter (~0.00027 deg lat, ~0.00028 deg lng)
        jitter_lat = random.uniform(-30.0, 30.0) / 111000.0
        jitter_lng = random.uniform(-30.0, 30.0) / 108000.0
        lat = round(base_lat + jitter_lat, 6)
        lng = round(base_lng + jitter_lng, 6)

        depth_cm = round(random.uniform(2.0, 25.0), 1)
        width_cm = round(random.uniform(15.0, 80.0), 1)
        length_cm = round(random.uniform(20.0, 120.0), 1)
        
        if depth_cm < 5.0:
            severity = "Low"
        elif depth_cm < 10.0:
            severity = "Medium"
        elif depth_cm < 18.0:
            severity = "High"
        else:
            severity = "Critical"

        confidence = round(random.uniform(0.65, 0.98), 2)

        if severity == "Low":
            repair_status = "Repaired" if random.random() < 0.60 else "Pending"
        else:
            repair_status = "Pending"

        defect_type = random.choice(["pothole", "pothole", "crack", "speedbump"])
        timestamp = now - random.randint(0, thirty_days_seconds)

        insert_defect(
            lat=lat,
            lng=lng,
            latitude=lat,
            longitude=lng,
            defect_type=defect_type,
            severity=severity,
            confidence=confidence,
            depth_cm=depth_cm,
            width_cm=width_cm,
            length_cm=length_cm,
            road_name=road_name,
            city="Bengaluru",
            detection_source="Simulation Drive",
            repair_status=repair_status,
            timestamp=timestamp
        )

    print("Seeding completed successfully!")
    
    # Run audit query
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*), COUNT(DISTINCT depth_cm), COUNT(DISTINCT lat), COUNT(DISTINCT road_name) 
        FROM defects;
    """)
    audit_res = cursor.fetchone()
    print("AUDIT QUERY RESULT:")
    print(f"COUNT(*): {audit_res[0]} | DISTINCT depth_cm: {audit_res[1]} | DISTINCT lat: {audit_res[2]} | DISTINCT road_name: {audit_res[3]}")
    conn.close()
    return audit_res

if __name__ == "__main__":
    seed_defects(1200)
