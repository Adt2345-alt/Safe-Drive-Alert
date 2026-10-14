"""
SafeDrive AI - Multi-Vehicle Fleet Seeding Script
Populates defects.db with 20 monitored vehicles (VH-001 to VH-020),
realistic Indian driver names, commercial vehicle models, route trajectories,
and assigns existing road defects to vehicles.
"""

import os
import sys
import time
import random

# Add workspace root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.api.defects_db import (
    get_db_connection,
    init_defects_db,
    BANGALORE_ROADS
)

INDIAN_DRIVER_NAMES = [
    "Rajesh Kumar", "Vikram Singh", "Priya Sharma", "Amit Patel", "Suresh Babu",
    "Ananya Rao", "Ramesh Hegde", "Karthik Nair", "Sunita Verma", "Mohammad Ali",
    "Deepa Gowda", "Ravi Teja", "Sanjay Dutt", "Vijay Kumar", "Lakshmi Prasad",
    "Rahul Deshmukh", "Pooja Reddy", "Manoj Tiwari", "Kavita Iyer", "Arjun Mehta"
]

VEHICLE_MODELS = [
    "Tata Ace Gold EV",
    "Mahindra Bolero Pik-Up",
    "Eicher Pro 2049",
    "Ashok Leyland Dost+",
    "Force Traveller 3350",
    "Tata 407 Gold SFC",
    "BharatBenz 1217C",
    "Isuzu D-Max V-Cross"
]

def seed_fleet():
    print("Initializing DB and seeding 20 multi-vehicle fleet units (VH-001 to VH-020)...")
    init_defects_db()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear existing vehicles and routes
    cursor.execute("DELETE FROM vehicles;")
    cursor.execute("DELETE FROM vehicle_routes;")
    conn.commit()

    now = int(time.time())
    roads_list = list(BANGALORE_ROADS.keys())

    # Pick exactly 15 active and 5 offline indices
    vehicle_indices = list(range(20))
    offline_indices = set(random.sample(vehicle_indices, 5))

    vehicles_data = []
    
    for i in range(20):
        v_id = f"VH-{i+1:03d}"
        driver = INDIAN_DRIVER_NAMES[i % len(INDIAN_DRIVER_NAMES)]
        model = random.choice(VEHICLE_MODELS)
        is_offline = i in offline_indices
        status = "offline" if is_offline else "active"

        # Assign a primary road corridor to vehicle
        primary_road = roads_list[i % len(roads_list)]
        (start_lat, start_lng), (end_lat, end_lng) = BANGALORE_ROADS[primary_road]
        
        t_pos = random.uniform(0.1, 0.9)
        current_lat = round(start_lat + t_pos * (end_lat - start_lat), 6)
        current_lng = round(start_lng + t_pos * (end_lng - start_lng), 6)

        if is_offline:
            # Last pinged 1 to 5 days ago
            last_ping = now - random.randint(86400, 432000)
        else:
            # Active: pinged within last 15 minutes (60 - 900s ago)
            last_ping = now - random.randint(60, 900)

        cursor.execute("""
            INSERT INTO vehicles (id, driver_name, model, status, last_ping, defects_detected, current_lat, current_lng, current_road)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (v_id, driver, model, status, last_ping, 0, current_lat, current_lng, primary_road))

        vehicles_data.append(v_id)

        # Generate 5-10 historical route pings for each vehicle along road corridors
        num_route_pts = random.randint(5, 12)
        for r_idx in range(num_route_pts):
            r_road = random.choice(roads_list)
            (r_start_lat, r_start_lng), (r_end_lat, r_end_lng) = BANGALORE_ROADS[r_road]
            rt = random.uniform(0.0, 1.0)
            r_lat = round(r_start_lat + rt * (r_end_lat - r_start_lat), 6)
            r_lng = round(r_start_lng + rt * (r_end_lng - r_start_lng), 6)
            
            # Timestamp up to 30 days ago
            r_ts = last_ping - random.randint(100, 2592000)
            cursor.execute("""
                INSERT INTO vehicle_routes (vehicle_id, road_name, lat, lng, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (v_id, r_road, r_lat, r_lng, r_ts))

    conn.commit()
    print(f"Created {len(vehicles_data)} vehicles (15 active / 5 offline).")

    # Assign each defect to a random vehicle
    defects = cursor.execute("SELECT id FROM defects").fetchall()
    if defects:
        defect_counts = {v_id: 0 for v_id in vehicles_data}
        for d in defects:
            assigned_v = random.choice(vehicles_data)
            cursor.execute("UPDATE defects SET vehicle_id = ? WHERE id = ?", (assigned_v, d['id']))
            defect_counts[assigned_v] += 1
        
        # Update defects_detected count in vehicles table
        for v_id, count in defect_counts.items():
            cursor.execute("UPDATE vehicles SET defects_detected = ? WHERE id = ?", (count, v_id))
        
        conn.commit()
        print(f"Successfully assigned {len(defects)} defects across {len(vehicles_data)} fleet vehicles.")
    else:
        print("No defects found in DB. Run seed_realistic_defects.py to populate defects first if desired.")

    # Audit verification query
    cursor.execute("SELECT status, COUNT(*) FROM vehicles GROUP BY status")
    status_summary = dict(cursor.fetchall())
    cursor.execute("SELECT SUM(defects_detected), COUNT(*) FROM vehicles")
    total_defects_assigned, total_v = cursor.fetchone()

    print("\n--- FLEET SEEDING AUDIT ---")
    print(f"Total Vehicles: {total_v}")
    print(f"Status Summary: {status_summary}")
    print(f"Total Defects Assigned to Vehicles: {total_defects_assigned}")

    conn.close()
    return total_v

if __name__ == "__main__":
    seed_fleet()
