import os
import sys
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.api.defects_db import get_db_connection, query_defects
from src.analytics.cost_calculator import calculate_defect_cost

def init_defect_costs_table(conn):
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS defect_costs (
        defect_id INTEGER PRIMARY KEY,
        volume_l REAL NOT NULL,
        asphalt_kg REAL NOT NULL,
        labor_min REAL NOT NULL,
        repair_cost REAL NOT NULL,
        damage_risk_annual REAL NOT NULL,
        net_savings REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("DELETE FROM defect_costs;")
    conn.commit()

def run_cost_calculation():
    conn = get_db_connection()
    init_defect_costs_table(conn)

    defects = query_defects(limit=10000)
    print(f"Loaded {len(defects)} defects from database for cost calculation...")

    cursor = conn.cursor()
    total_repair_cost = 0.0
    total_damage_risk = 0.0
    total_net_savings = 0.0

    for d in defects:
        raw_id = d["raw_id"]
        cost_data = calculate_defect_cost(d)

        cursor.execute("""
        INSERT INTO defect_costs (defect_id, volume_l, asphalt_kg, labor_min, repair_cost, damage_risk_annual, net_savings)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            raw_id,
            cost_data["volume_l"],
            cost_data["asphalt_kg"],
            cost_data["labor_min"],
            cost_data["repair_cost"],
            cost_data["damage_risk_annual"],
            cost_data["net_savings"]
        ))

        total_repair_cost += cost_data["repair_cost"]
        total_damage_risk += cost_data["damage_risk_annual"]
        total_net_savings += cost_data["net_savings"]

    conn.commit()
    conn.close()

    print("\n===========================================================")
    print("DEFECT COST & RISK SAVINGS CALCULATION SUMMARY")
    print("===========================================================")
    print(f"Total Defects Processed: {len(defects)}")
    print(f"Total Estimated Repair Cost: ${total_repair_cost:,.2f}")
    print(f"Total Annual Damage Risk:   ${total_damage_risk:,.2f}")
    print(f"NET POTENTIAL SAVINGS:      ${total_net_savings:,.2f}")
    print("===========================================================")

if __name__ == "__main__":
    run_cost_calculation()
