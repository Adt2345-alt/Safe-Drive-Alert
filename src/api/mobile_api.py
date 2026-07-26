from flask import Blueprint, jsonify, request
import time
from src.utils.logger import LogManager
from src.utils.auth_helper import requires_auth
from src.utils.db import report_defect as db_report_defect, log_audit

# Define blueprint
mobile_api_bp = Blueprint('mobile_api', __name__)
logger = LogManager.get_system_logger()

# Reference to the system manager, set during startup in main
sys_manager = None

def init_mobile_api(manager):
    global sys_manager
    sys_manager = manager

@mobile_api_bp.route('/api/mobile/status', methods=['GET'])
@requires_auth()
def get_mobile_status():
    """
    Returns live vehicle status, including position, speed, and active alerts.
    """
    if sys_manager is None:
        return jsonify({"error": "System not initialized"}), 500
        
    telemetry = sys_manager.gps.get_telemetry()
    active_alert = sys_manager.alert_system.active_alert
    
    return jsonify({
        "timestamp": time.time(),
        "vehicle_id": "V-9872",
        "latitude": telemetry["latitude"],
        "longitude": telemetry["longitude"],
        "speed_kmh": telemetry["speed_kmh"],
        "heading": telemetry["heading"],
        "alert_active": active_alert is not None,
        "current_alert": active_alert
    })

@mobile_api_bp.route('/api/mobile/defects', methods=['GET'])
@requires_auth()
def get_mobile_defects():
    """
    Returns list of all logged road defects recorded during the drive.
    """
    if sys_manager is None:
        return jsonify({"error": "System not initialized"}), 500
        
    return jsonify({
        "count": len(sys_manager.metrics.detections_history),
        "defects": sys_manager.metrics.detections_history
    })

@mobile_api_bp.route('/api/mobile/report', methods=['POST'])
@requires_auth()
def report_defect():
    """
    Endpoint for mobile clients to manually report a road defect.
    Inserts a new obstacle dynamically into the simulated road environment and SQL DB!
    """
    if sys_manager is None:
        return jsonify({"error": "System not initialized"}), 500
        
    data = request.get_json() or {}
    
    defect_type = data.get("type")
    lat = data.get("latitude")
    lon = data.get("longitude")
    severity = data.get("severity", "medium")
    
    if not defect_type or lat is None or lon is None:
        return jsonify({"error": "Missing required fields: type, latitude, longitude"}), 400
        
    if defect_type not in ["pothole", "speed_bump"]:
        return jsonify({"error": "Invalid defect type. Must be 'pothole' or 'speed_bump'"}), 400
        
    # Project the reported GPS coordinates back onto the simulator path
    sim = sys_manager.road_sim
    closest_distance = 0.0
    min_dist = float('inf')
    
    for i in range(len(sim.route) - 1):
        coord = sim.route[i]
        d = sim._distance_between_coords((lat, lon), coord)
        if d < min_dist:
            min_dist = d
            accumulated = 0.0
            for j in range(i):
                accumulated += sim._distance_between_coords(sim.route[j], sim.route[j+1])
            closest_distance = accumulated
            
    # Check if we already have an obstacle close by
    for obs in sim.obstacles:
        dist_diff = abs(obs["distance"] - closest_distance)
        if dist_diff < 15.0:
            return jsonify({"status": "duplicate", "message": "Obstacle already exists near this location"}), 200

    new_id = len(sim.obstacles) + 1
    # Add new obstacle dynamically to simulator
    new_obstacle = {
        "id": new_id,
        "type": defect_type,
        "distance": closest_distance,
        "lateral_offset": 0.0,
        "severity": severity,
        "gps": (lat, lon),
        "heading": 0.0,
        "detected": False
    }
    sim.obstacles.append(new_obstacle)
    
    # Save to SQLite DB
    db_report_defect(defect_type, lat, lon, severity, "unresolved", request.user["username"])
    
    # Audit log
    log_audit(
        request.user["username"], 
        request.user["role"], 
        "MOBILE_REPORT_DEFECT", 
        f"Reported new {defect_type.upper()} at ({lat:.5f}, {lon:.5f})"
    )
    
    logger.info(f"Mobile Report by {request.user['username']}: Registered new {defect_type.upper()} [ID: {new_id}] at ({lat:.6f}, {lon:.6f}) via mobile API")
    
    return jsonify({
        "status": "success",
        "message": f"Successfully registered manually reported {defect_type}",
        "obstacle": {
            "id": new_id,
            "type": defect_type,
            "latitude": lat,
            "longitude": lon,
            "severity": severity
        }
    }), 201
