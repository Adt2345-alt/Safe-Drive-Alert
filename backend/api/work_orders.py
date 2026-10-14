"""
SafeDrive AI - Work Orders API Blueprint
Manages work order generation, grouping defects by road corridor, assigning crews,
updating status, and exporting ReportLab PDF reports.
"""

import os
import sys
import time
import math
import logging
from typing import List, Dict, Any
from flask import Blueprint, jsonify, request, send_file, make_response

logger = logging.getLogger("SafeDrive.WorkOrdersAPI")
logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.api.defects_db import get_db_connection, query_defects
from src.analytics.cost_calculator import calculate_defect_cost
from src.reports.work_order_pdf import generate_work_order_pdf

work_orders_bp = Blueprint('work_orders_bp', __name__)

# In-memory / DB store helper
def init_work_orders_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS generated_work_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        work_order_code TEXT UNIQUE NOT NULL,
        region TEXT DEFAULT 'Bangalore',
        road_name TEXT NOT NULL,
        defect_count INTEGER NOT NULL,
        total_cost REAL NOT NULL,
        total_labor_hours REAL NOT NULL,
        priority TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        crew_size INTEGER DEFAULT 1,
        crew_name TEXT DEFAULT 'Unassigned',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()

init_work_orders_table()

SEVERITY_WEIGHTS = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}

@work_orders_bp.route('/api/work-orders/generate', methods=['POST'])
def generate_work_orders():
    """Generates work orders by grouping defects by road corridor and calculating total labor & costs."""
    data = request.get_json() or {}
    region = data.get('region', 'Bangalore')
    min_severity = data.get('min_severity', 'Medium')

    min_weight = SEVERITY_WEIGHTS.get(min_severity, 2)

    all_defects = query_defects(limit=10000)
    
    # Filter defects by min_severity
    filtered_defects = []
    for d in all_defects:
        sev = d.get('severity', 'Medium')
        w = SEVERITY_WEIGHTS.get(sev, 2)
        if w >= min_weight:
            filtered_defects.append(d)

    # Group by road_name
    road_groups: Dict[str, List[Dict[str, Any]]] = {}
    for d in filtered_defects:
        r = d.get('road_name') or d.get('corridor') or 'MG Road Corridor'
        if r not in road_groups:
            road_groups[r] = []
        road_groups[r].append(d)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM generated_work_orders;")
    conn.commit()

    generated_orders = []
    year = time.strftime("%Y")
    idx = 1

    total_overall_cost = 0.0
    total_overall_hours = 0.0

    # Process each road corridor as a distinct work order
    for road_name, defects_list in road_groups.items():
        wo_code = f"WO-{year}-{idx:04d}"
        
        road_total_cost = 0.0
        road_total_labor_min = 0.0
        has_critical = False
        has_high = False

        for d in defects_list:
            c_info = calculate_defect_cost(d)
            road_total_cost += c_info["repair_cost"]
            road_total_labor_min += c_info["labor_min"]
            
            if d.get("severity") == "Critical":
                has_critical = True
            elif d.get("severity") == "High":
                has_high = True

        labor_hours = round(road_total_labor_min / 60.0, 1)
        crew_size = max(1, math.ceil(labor_hours / 8.0))

        if has_critical:
            priority = "CRITICAL"
        elif has_high:
            priority = "HIGH"
        elif min_severity == "Low":
            priority = "LOW"
        else:
            priority = "MEDIUM"

        crew_name = f"Team {chr(65 + ((idx - 1) % 6))}"

        cursor.execute("""
        INSERT INTO generated_work_orders (work_order_code, region, road_name, defect_count, total_cost, total_labor_hours, priority, status, crew_size, crew_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (wo_code, region, road_name, len(defects_list), round(road_total_cost, 2), labor_hours, priority, "Pending", crew_size, crew_name))

        order_id = cursor.lastrowid

        wo_obj = {
            "id": order_id,
            "work_order_code": wo_code,
            "region": region,
            "road_name": road_name,
            "defect_count": len(defects_list),
            "total_cost": round(road_total_cost, 2),
            "total_labor_hours": labor_hours,
            "priority": priority,
            "status": "Pending",
            "crew_size": crew_size,
            "crew_name": crew_name,
            "defects": defects_list
        }

        generated_orders.append(wo_obj)
        total_overall_cost += road_total_cost
        total_overall_hours += labor_hours
        idx += 1

    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "region": region,
        "min_severity": min_severity,
        "work_orders_count": len(generated_orders),
        "summary": {
            "total_orders": len(generated_orders),
            "total_cost": round(total_overall_cost, 2),
            "total_hours": round(total_overall_hours, 1)
        },
        "work_orders": generated_orders
    })

@work_orders_bp.route('/api/work-orders', methods=['GET'])
def list_work_orders():
    """Lists all stored work orders from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM generated_work_orders ORDER BY id ASC;").fetchall()
    conn.close()

    orders = [dict(r) for r in rows]
    return jsonify({
        "status": "success",
        "count": len(orders),
        "work_orders": orders
    })

@work_orders_bp.route('/api/work-orders/<int:order_id>/status', methods=['PUT'])
def update_work_order_status_by_id(order_id: int):
    """Updates status and crew_name of a work order."""
    data = request.get_json() or {}
    new_status = data.get('status', 'Assigned')
    crew_name = data.get('crew_name')

    conn = get_db_connection()
    cursor = conn.cursor()
    if crew_name:
        cursor.execute("UPDATE generated_work_orders SET status = ?, crew_name = ? WHERE id = ? OR work_order_code = ?", (new_status, crew_name, order_id, f"WO-2026-{order_id:04d}"))
    else:
        cursor.execute("UPDATE generated_work_orders SET status = ? WHERE id = ? OR work_order_code = ?", (new_status, order_id, f"WO-2026-{order_id:04d}"))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": f"Work order {order_id} updated to {new_status}"
    })

@work_orders_bp.route('/api/work-orders/export-pdf', methods=['GET'])
def export_work_orders_pdf():
    """Generates and downloads the executive PDF report."""
    region = request.args.get('region', 'Bangalore')

    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM generated_work_orders ORDER BY id ASC;").fetchall()
    conn.close()

    wos = [dict(r) for r in rows]

    # If no generated work orders exist, generate dynamically
    if not wos:
        defects = query_defects(limit=10000)
        road_groups = {}
        for d in defects:
            r = d.get('road_name') or 'Corridor'
            if r not in road_groups:
                road_groups[r] = []
            road_groups[r].append(d)

        idx = 1
        for road, d_list in road_groups.items():
            total_cost = sum(calculate_defect_cost(d)["repair_cost"] for d in d_list)
            total_labor_min = sum(calculate_defect_cost(d)["labor_min"] for d in d_list)
            total_hours = total_labor_min / 60.0
            
            has_critical = any(d['severity'] == 'Critical' for d in d_list)
            has_high = any(d['severity'] == 'High' for d in d_list)
            priority = "CRITICAL" if has_critical else ("HIGH" if has_high else "MEDIUM")

            wos.append({
                "work_order_code": f"WO-2026-{idx:04d}",
                "road_name": road,
                "defect_count": len(d_list),
                "total_cost": total_cost,
                "total_labor_hours": total_hours,
                "priority": priority,
                "defects": d_list
            })
            idx += 1
    else:
        # Attach defect lists to work orders
        all_defects = query_defects(limit=10000)
        for wo in wos:
            wo_defects = [d for d in all_defects if (d.get('road_name') or d.get('corridor')) == wo['road_name']]
            wo['defects'] = wo_defects

    pdf_file_path = generate_work_order_pdf(wos, region=region)
    date_str = time.strftime("%Y-%m-%d")

    return send_file(
        pdf_file_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"WorkOrders_{region}_{date_str}.pdf"
    )
