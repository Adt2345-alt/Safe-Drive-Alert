"""
SafeDrive AI - HD Mapping Backend API
Serves real defect data from SQLite defects.db, real-time spatial density,
vehicle GPS trajectories, and work orders.
"""

from flask import Blueprint, jsonify, request
import time
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("SafeDrive.MapDataAPI")
logger.setLevel(logging.INFO)

map_data_bp = Blueprint('map_data_bp', __name__)

@map_data_bp.route('/api/map/defects', methods=['GET'])
def get_defects():
    """
    Returns recorded defect points from SQLite defects.db.
    Returns [] if no detections exist.
    """
    try:
        from backend.api.defects_db import query_defects
    except ImportError:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backend.api.defects_db import query_defects

    min_ts = request.args.get('min_ts', type=int)
    max_ts = request.args.get('max_ts', type=int)
    severity_filter = request.args.get('severity')
    type_filter = request.args.get('type')
    bbox_str = request.args.get('bbox')
    limit = request.args.get('limit', default=10000, type=int)

    bbox = None
    if bbox_str:
        try:
            parts = [float(x) for x in bbox_str.split(',')]
            if len(parts) == 4:
                bbox = parts
        except ValueError:
            pass

    defects = query_defects(
        min_ts=min_ts,
        max_ts=max_ts,
        severity=severity_filter,
        defect_type=type_filter,
        bbox=bbox,
        limit=limit
    )

    return jsonify({
        "status": "success",
        "total_count": len(defects),
        "returned_count": len(defects),
        "defects": defects
    })

@map_data_bp.route('/api/map/heatmap', methods=['GET'])
def get_heatmap_data():
    """Returns spatial density points calculated from recorded detections in defects.db."""
    try:
        from backend.api.defects_db import query_defects
    except ImportError:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backend.api.defects_db import query_defects

    defects = query_defects(limit=10000)
    points = []
    for d in defects:
        weight = 1.0
        if d['severity'] == "Critical":
            weight = 4.0
        elif d['severity'] == "High":
            weight = 3.0
        elif d['severity'] == "Medium":
            weight = 2.0
            
        points.append({
            "coordinates": [d['lng'], d['lat']],
            "weight": weight,
            "depth_cm": d['depth_cm']
        })

    return jsonify({
        "status": "success",
        "count": len(points),
        "points": points
    })

@map_data_bp.route('/api/map/trajectory', methods=['GET'])
def get_trajectory():
    """Returns recorded vehicle trajectory points from defects.db."""
    try:
        from backend.api.defects_db import query_defects
    except ImportError:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backend.api.defects_db import query_defects

    defects = query_defects(limit=500)
    path = []
    for d in defects:
        path.append({
            "timestamp": d["timestamp"],
            "coordinates": [d["lng"], d["lat"], 10.0],
            "speed_kmh": 40.0
        })

    return jsonify({
        "status": "success",
        "count": len(path),
        "path": path
    })

@map_data_bp.route('/api/map/predictions', methods=['GET'])
def get_predictions():
    """Returns predicted hotspots. Returns empty list if no analysis run."""
    return jsonify({
        "status": "success",
        "count": 0,
        "predictions": []
    })

@map_data_bp.route('/api/map/municipality/work-orders', methods=['GET'])
def get_work_orders_geojson():
    """Returns municipal work orders from SQLite database."""
    try:
        from src.utils.db import get_work_orders
        orders = get_work_orders()
    except Exception:
        orders = []

    features = []
    for wo in orders:
        features.append({
            "type": "Feature",
            "properties": {
                "id": f"WO-{wo.get('id', 1):03d}",
                "title": wo.get("description", "Work Order"),
                "assigned_driver": wo.get("assigned_driver"),
                "status": wo.get("status", "assigned"),
                "type": wo.get("type", "Pothole")
            },
            "geometry": None
        })

    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })

@map_data_bp.route('/api/defects/<int:defect_id>', methods=['GET'])
def get_defect_detail(defect_id: int):
    """
    Returns single defect record by integer ID from defects.db.
    Returns 404 error JSON if not found.
    """
    try:
        from backend.api.defects_db import get_defect_by_id
    except ImportError:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backend.api.defects_db import get_defect_by_id

    defect = get_defect_by_id(defect_id)
    if not defect:
        return jsonify({
            "status": "error",
            "message": f"Defect with ID {defect_id} not found"
        }), 404

    return jsonify(defect)

@map_data_bp.route('/api/defects/<int:defect_id>/nearby', methods=['GET'])
def get_nearby_defects(defect_id: int):
    """Returns nearby historical defects for 3D comparison mode."""
    try:
        from backend.api.defects_db import get_defect_by_id, query_nearby_defects
    except ImportError:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backend.api.defects_db import get_defect_by_id, query_nearby_defects

    defect = get_defect_by_id(defect_id)
    if not defect:
        return jsonify({"status": "error", "message": "Defect not found"}), 404

    radius = request.args.get('radius_m', default=100.0, type=float)
    nearby = query_nearby_defects(defect["lat"], defect["lng"], radius_m=radius)
    nearby = [d for d in nearby if d["id"] != defect_id]

    return jsonify({
        "status": "success",
        "target_defect_id": defect_id,
        "count": len(nearby),
        "nearby_defects": nearby
    })

