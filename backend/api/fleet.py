"""
SafeDrive AI - Multi-Vehicle Fleet Telemetry & Coverage API
Serves fleet status, vehicle telemetry details, live map locations,
and road network coverage metrics.
"""

from flask import Blueprint, jsonify, request
import logging
from typing import Dict, Any

logger = logging.getLogger("SafeDrive.FleetAPI")
logger.setLevel(logging.INFO)

fleet_bp = Blueprint('fleet_bp', __name__)

def _get_db_helpers():
    try:
        from backend.api.defects_db import (
            get_vehicles,
            get_vehicle_by_id,
            get_vehicle_routes,
            get_fleet_coverage
        )
        return get_vehicles, get_vehicle_by_id, get_vehicle_routes, get_fleet_coverage
    except ImportError:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backend.api.defects_db import (
            get_vehicles,
            get_vehicle_by_id,
            get_vehicle_routes,
            get_fleet_coverage
        )
        return get_vehicles, get_vehicle_by_id, get_vehicle_routes, get_fleet_coverage

@fleet_bp.route('/api/fleet/vehicles', methods=['GET'])
def list_vehicles():
    """
    Returns all monitored fleet units with driver, model, status, last ping, and defect metrics.
    Supports optional status filter ?status=active|offline|all.
    """
    get_vehicles_fn, _, _, _ = _get_db_helpers()
    status_filter = request.args.get('status')
    
    vehicles = get_vehicles_fn(status=status_filter)
    all_vehicles = get_vehicles_fn() if status_filter else vehicles

    active_count = sum(1 for v in all_vehicles if v["status"].lower() == "active")
    offline_count = sum(1 for v in all_vehicles if v["status"].lower() == "offline")

    return jsonify({
        "status": "success",
        "total_count": len(all_vehicles),
        "active_count": active_count,
        "offline_count": offline_count,
        "returned_count": len(vehicles),
        "vehicles": vehicles
    })

@fleet_bp.route('/api/fleet/vehicles/<vehicle_id>', methods=['GET'])
def vehicle_detail(vehicle_id: str):
    """
    Returns full telemetry detail for a single vehicle unit by ID (e.g., VH-001).
    Includes metadata, list of assigned defects, and historical route trajectory.
    """
    _, get_vehicle_by_id_fn, _, _ = _get_db_helpers()
    vehicle = get_vehicle_by_id_fn(vehicle_id)

    if not vehicle:
        return jsonify({
            "status": "error",
            "message": f"Vehicle with ID '{vehicle_id}' not found"
        }), 404

    return jsonify({
        "status": "success",
        "vehicle": vehicle
    })

@fleet_bp.route('/api/fleet/live-map', methods=['GET'])
def live_map_positions():
    """
    Returns real-time GPS dots / locations of all fleet vehicles for map overlay.
    """
    get_vehicles_fn, _, _, _ = _get_db_helpers()
    vehicles = get_vehicles_fn()

    map_dots = []
    for v in vehicles:
        map_dots.append({
            "id": v["id"],
            "driver_name": v["driver_name"],
            "model": v["model"],
            "status": v["status"],
            "last_ping": v["last_ping"],
            "last_ping_formatted": v["last_ping_formatted"],
            "defects_detected": v["defects_detected"],
            "lat": v["current_lat"],
            "lng": v["current_lng"],
            "current_road": v["current_road"]
        })

    return jsonify({
        "status": "success",
        "count": len(map_dots),
        "vehicles": map_dots
    })

@fleet_bp.route('/api/fleet/coverage', methods=['GET'])
def fleet_road_coverage():
    """
    Calculates city road network scanning coverage over the last N days (default 7 days).
    Categorizes road segments into green (scanned <=7d), yellow (<=30d), red (>30d/never).
    """
    _, _, _, get_fleet_coverage_fn = _get_db_helpers()
    days_arg = request.args.get('days', default=7, type=int)

    coverage_data = get_fleet_coverage_fn(days=days_arg)
    return jsonify(coverage_data)
