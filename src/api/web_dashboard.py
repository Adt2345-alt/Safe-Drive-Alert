from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, make_response
from flask_cors import CORS
import cv2
import time
import os
import csv
import io

from src.utils.config import Config
from src.utils.logger import LogManager
from src.utils.db import (
    get_user_by_username, verify_password, log_audit, create_user,
    delete_user, get_all_users, get_audit_logs, create_work_order,
    get_work_orders, update_work_order_status, report_defect, get_defects, hash_password
)
from src.utils.jwt_helper import encode_jwt
from src.utils.auth_helper import requires_auth, get_current_user, ROLE_PERMISSIONS
from src.api.mobile_api import mobile_api_bp, init_mobile_api
try:
    from backend.api.map_data import map_data_bp
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from backend.api.map_data import map_data_bp

from src.core.upload_processor import UploadProcessor
from src.analytics.clustering import HotspotClusterer
from src.analytics.prediction import PotholeGrowthPredictor
from src.analytics.weather_integration import WeatherCorrelator
from src.analytics.traffic_integration import TrafficImpactAnalyzer
from src.analytics.risk_scorer import RouteRiskScorer

app = Flask(__name__, template_folder="templates")
CORS(app)

# Configure upload directory
UPLOAD_FOLDER = os.path.join(Config.DATA_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Register mobile API and Map Data blueprints
app.register_blueprint(mobile_api_bp)
app.register_blueprint(map_data_bp)

logger = LogManager.get_system_logger()
sys_manager = None
active_upload_processor = None

def init_web_server(manager):
    global sys_manager
    sys_manager = manager
    init_mobile_api(manager)

# --- AUTH ROUTES ---

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "VIEWER")
    region = data.get("region", "Global")
    
    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400
        
    username = username.strip()
    if not username:
        return jsonify({"error": "Invalid username"}), 400
        
    if role not in ROLE_PERMISSIONS:
        return jsonify({"error": "Invalid role specified"}), 400
        
    pw_hash = hash_password(password)
    success = create_user(username, pw_hash, role, region)
    
    if success:
        log_audit(username, role, "USER_REGISTER", f"Self-registered account with role {role}")
        return jsonify({"status": "success", "message": "Account created successfully!"}), 201
    else:
        return jsonify({"error": "Username already exists"}), 409

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() or {}
        username = data.get("username")
        password = data.get("password")
        
        if not username or not password:
            return jsonify({"error": "Missing credentials"}), 400
            
        user = get_user_by_username(username)
        if not user or not verify_password(password, user["password_hash"]):
            log_audit(username, "UNKNOWN", "LOGIN_FAILED", "Failed login attempt: Invalid security credentials")
            return jsonify({"error": "Access Denied: Invalid credentials"}), 401
            
        log_audit(user["username"], user["role"], "LOGIN_SUCCESS", f"User logged in from IP {request.remote_addr}")
        
        token = encode_jwt({
            "username": user["username"],
            "role": user["role"],
            "region": user["region"],
            "exp": time.time() + 86400  # 24 hours
        })
        
        response = make_response(jsonify({"status": "success", "role": user["role"], "token": token}))
        response.set_cookie("access_token", token, max_age=86400, httponly=True, samesite="Lax")
        return response
        
    return render_template('login.html')

@app.route('/logout', methods=['POST', 'GET'])
def logout():
    user = get_current_user()
    if user:
        log_audit(user["username"], user["role"], "LOGOUT", "User logged out")
    response = make_response(redirect(url_for('login')))
    response.delete_cookie("access_token")
    return response

@app.route('/api/user/me', methods=['GET'])
@requires_auth()
def get_user_me():
    user = request.user
    return jsonify({
        "username": user["username"],
        "role": user["role"],
        "region": user.get("region"),
        "permissions": ROLE_PERMISSIONS.get(user["role"], [])
    })

# --- USER MANAGEMENT (Admin Only) ---

@app.route('/api/admin/users', methods=['GET', 'POST'])
@requires_auth(permission='manage_users')
def manage_users_api():
    if request.method == 'GET':
        return jsonify(get_all_users())
    
    # POST - Create User
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role")
    region = data.get("region", "Global")
    
    if not username or not password or not role:
        return jsonify({"error": "Missing required fields: username, password, role"}), 400
        
    if role not in ROLE_PERMISSIONS:
        return jsonify({"error": f"Invalid role. Must be one of {list(ROLE_PERMISSIONS.keys())}"}), 400
        
    pw_hash = hash_password(password)
    success = create_user(username, pw_hash, role, region)
    
    if success:
        log_audit(request.user["username"], request.user["role"], "USER_CREATE", f"Created user {username} with role {role}")
        return jsonify({"status": "success", "message": f"User {username} created successfully"}), 201
    else:
        return jsonify({"error": "Username already exists"}), 409

@app.route('/api/admin/users/<username>', methods=['DELETE'])
@requires_auth(permission='manage_users')
def delete_user_api(username):
    if username == request.user["username"]:
        return jsonify({"error": "Cannot delete your own admin account"}), 400
        
    delete_user(username)
    log_audit(request.user["username"], request.user["role"], "USER_DELETE", f"Deleted user {username}")
    return jsonify({"status": "success", "message": f"User {username} deleted successfully"})

# --- AUDIT LOGS (Admin Only) ---

@app.route('/api/admin/logs', methods=['GET'])
@requires_auth(permission='manage_users')
def get_audit_logs_api():
    return jsonify(get_audit_logs())

# --- SYSTEM CONFIG & SETTINGS (Admin Only) ---

@app.route('/api/admin/settings', methods=['GET', 'POST'])
@requires_auth(permission='system_settings')
def system_settings_api():
    if request.method == 'GET':
        return jsonify({
            "FPS": Config.FPS,
            "ALERT_TRIGGER_DISTANCE": Config.ALERT_TRIGGER_DISTANCE,
            "COOLDOWN_PERIOD_SECONDS": Config.COOLDOWN_PERIOD_SECONDS,
            "DETECTION_CONF_THRESHOLD": Config.DETECTION_CONF_THRESHOLD
        })
        
    data = request.get_json() or {}
    try:
        if "FPS" in data:
            Config.FPS = int(data["FPS"])
        if "ALERT_TRIGGER_DISTANCE" in data:
            Config.ALERT_TRIGGER_DISTANCE = float(data["ALERT_TRIGGER_DISTANCE"])
        if "COOLDOWN_PERIOD_SECONDS" in data:
            Config.COOLDOWN_PERIOD_SECONDS = float(data["COOLDOWN_PERIOD_SECONDS"])
        if "DETECTION_CONF_THRESHOLD" in data:
            Config.DETECTION_CONF_THRESHOLD = float(data["DETECTION_CONF_THRESHOLD"])
            
        log_audit(request.user["username"], request.user["role"], "CONFIG_UPDATE", f"Updated settings: {data}")
        return jsonify({"status": "success", "message": "System settings updated successfully"})
    except ValueError:
        return jsonify({"error": "Invalid configurations format"}), 400

# --- ALERTS ACKNOWLEDGEMENT ---

@app.route('/api/alerts/acknowledge', methods=['POST'])
@requires_auth(permission='acknowledge_alerts')
def acknowledge_alert():
    if sys_manager and sys_manager.alert_system:
        alert = sys_manager.alert_system.active_alert
        if alert:
            log_audit(
                request.user["username"], 
                request.user["role"], 
                "ACKNOWLEDGE_ALERT", 
                f"Acknowledged alert ID {alert.get('id')} ({alert.get('type')})"
            )
            sys_manager.alert_system.active_alert = None
            return jsonify({"status": "success", "message": "Active alert acknowledged/resolved"})
        return jsonify({"status": "no_active_alert", "message": "No active warning alert found"}), 200
    return jsonify({"error": "System not initialized"}), 500

# --- WORK ORDER ASSIGNMENTS (Operator/Municipality/Admin) ---

@app.route('/api/work_orders', methods=['GET', 'POST'])
@requires_auth(permission='submit_reports')
def work_orders_api():
    if request.method == 'GET':
        return jsonify(get_work_orders())
        
    data = request.get_json() or {}
    obstacle_id = data.get("obstacle_id")
    obs_type = data.get("type")
    description = data.get("description", "")
    assigned_driver = data.get("assigned_driver")
    
    if not obs_type or not assigned_driver:
        return jsonify({"error": "Missing required fields: type, assigned_driver"}), 400
        
    create_work_order(obstacle_id, obs_type, description, assigned_driver)
    log_audit(
        request.user["username"], 
        request.user["role"], 
        "CREATE_WORK_ORDER", 
        f"Assigned {obs_type} repair task to {assigned_driver}"
    )
    return jsonify({"status": "success", "message": "Work order task created successfully"}), 201

@app.route('/api/work_orders/<int:order_id>', methods=['PUT'])
@requires_auth()
def update_work_order_api(order_id):
    data = request.get_json() or {}
    status = data.get("status")
    if not status:
        return jsonify({"error": "Missing field: status"}), 400
        
    update_work_order_status(order_id, status)
    log_audit(
        request.user["username"], 
        request.user["role"], 
        "UPDATE_WORK_ORDER", 
        f"Updated work order #{order_id} status to {status}"
    )
    return jsonify({"status": "success", "message": f"Work order status set to {status}"})

# --- DATA EXPORT (Operator/Municipality/Admin) ---

@app.route('/api/export', methods=['GET'])
@requires_auth(permission='export_data')
def export_data_api():
    export_format = request.args.get("format", "csv").lower()
    defects = get_defects()
    
    if sys_manager and sys_manager.metrics:
        for d in sys_manager.metrics.detections_history:
            if not any(abs(df["latitude"] - d["latitude"]) < 0.0001 and abs(df["longitude"] - d["longitude"]) < 0.0001 for df in defects):
                defects.append({
                    "id": d.get("id", 0),
                    "type": d["class"],
                    "latitude": d["latitude"],
                    "longitude": d["longitude"],
                    "severity": d["severity"],
                    "status": "unresolved",
                    "reported_by": "AI Detector",
                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(d.get("timestamp", time.time())))
                })
                
    if export_format == "json":
        return jsonify(defects)
        
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["ID", "Type", "Latitude", "Longitude", "Severity", "Status", "Reported By", "Timestamp"])
    for df in defects:
        cw.writerow([
            df.get("id"),
            df.get("type"),
            df.get("latitude"),
            df.get("longitude"),
            df.get("severity"),
            df.get("status"),
            df.get("reported_by"),
            df.get("timestamp")
        ])
        
    response = make_response(si.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=road_defects_report.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

# --- ORIGINAL CORE ROUTINGS ---

@app.route('/')
@requires_auth()
def index():
    role = request.user.get("role")
    if role == "DRIVER":
        return render_template('mobile.html')
    return render_template('index.html')

@app.route('/map')
@requires_auth()
def map_view():
    return render_template('map_view.html')

def stream_video():
    while True:
        if sys_manager is None:
            time.sleep(0.1)
            continue
            
        frame = sys_manager.get_latest_frame()
        if frame is None:
            time.sleep(0.04)
            continue
            
        success, encoded_image = cv2.imencode('.jpg', frame)
        if not success:
            time.sleep(0.04)
            continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + encoded_image.tobytes() + b'\r\n')
               
        time.sleep(1.0 / Config.FPS)

@app.route('/video_feed')
@requires_auth(permission='live_feed')
def video_feed():
    return Response(stream_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

def stream_depth_video():
    while True:
        if sys_manager is None:
            time.sleep(0.1)
            continue
            
        frame = sys_manager.get_latest_depth_frame()
        if frame is None:
            time.sleep(0.04)
            continue
            
        success, encoded_image = cv2.imencode('.jpg', frame)
        if not success:
            time.sleep(0.04)
            continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + encoded_image.tobytes() + b'\r\n')
               
        time.sleep(1.0 / Config.FPS)

@app.route('/depth_feed')
@requires_auth(permission='live_feed')
def depth_feed():
    return Response(stream_depth_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

def stream_upload_video():
    global active_upload_processor
    while True:
        if active_upload_processor is None:
            time.sleep(0.1)
            continue
        frame = active_upload_processor.get_latest_frame()
        if frame is None:
            time.sleep(0.04)
            continue
        success, encoded_image = cv2.imencode('.jpg', frame)
        if not success:
            time.sleep(0.04)
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + encoded_image.tobytes() + b'\r\n')
        
        time.sleep(1.0 / active_upload_processor.fps)

@app.route('/video_feed_upload')
@requires_auth(permission='live_feed')
def video_feed_upload():
    return Response(stream_upload_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/upload', methods=['POST'])
@requires_auth(permission='submit_reports')
def upload_video():
    global active_upload_processor
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if file:
        safe_filename = "".join([c for c in file.filename if c.isalnum() or c in ['.', '_', '-']]).strip()
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        file.save(file_path)
        logger.info(f"Video uploaded successfully to: {file_path}")
        
        if active_upload_processor:
            active_upload_processor.stop()
            
        active_upload_processor = UploadProcessor(file_path)
        active_upload_processor.start()
        
        log_audit(request.user["username"], request.user["role"], "VIDEO_UPLOAD", f"Uploaded video analyzer file: {safe_filename}")
        
        return jsonify({
            "status": "success", 
            "filename": safe_filename,
            "total_frames": active_upload_processor.total_frames
        })

@app.route('/api/upload/status', methods=['GET'])
@requires_auth(permission='view_dashboard')
def upload_status():
    global active_upload_processor
    if active_upload_processor is None:
        return jsonify({"status": "no_upload"})
    return jsonify(active_upload_processor.get_progress())

@app.route('/api/upload/detections', methods=['GET'])
@requires_auth(permission='view_dashboard')
def upload_detections():
    global active_upload_processor
    if active_upload_processor is None:
        return jsonify({"detections": []})
    return jsonify({
        "detections": active_upload_processor.detections_log
    })

@app.route('/api/telemetry', methods=['GET'])
@requires_auth(permission='view_dashboard')
def get_telemetry():
    if sys_manager is None:
        return jsonify({"error": "System not initialized"}), 500
        
    gps_data = sys_manager.gps.get_telemetry()
    active_alert = sys_manager.alert_system.active_alert
    metrics = sys_manager.metrics.get_summary()
    
    obstacles_summary = []
    for obs in sys_manager.road_sim.obstacles:
        obstacles_summary.append({
            "id": obs["id"],
            "type": obs["type"],
            "latitude": obs["gps"][0],
            "longitude": obs["gps"][1],
            "severity": obs["severity"],
            "distance_m": round((obs["distance"] - sys_manager.road_sim.current_distance) % sys_manager.road_sim.total_path_length_meters, 1),
            "detected": obs["detected"]
        })
        
    db_defects = get_defects()
    for db_d in db_defects:
        if not any(abs(obs["gps"][0] - db_d["latitude"]) < 0.0001 and abs(obs["gps"][1] - db_d["longitude"]) < 0.0001 for obs in sys_manager.road_sim.obstacles):
            obstacles_summary.append({
                "id": 1000 + db_d["id"],
                "type": db_d["type"],
                "latitude": db_d["latitude"],
                "longitude": db_d["longitude"],
                "severity": db_d["severity"],
                "distance_m": 999.0,
                "detected": db_d["status"] == "resolved"
            })
            
    return jsonify({
        "timestamp": time.time(),
        "telemetry": gps_data,
        "metrics": metrics,
        "active_alert": active_alert,
        "obstacles": obstacles_summary,
        "route_points": sys_manager.road_sim.route,
        "scenario": sys_manager.road_sim.scenario_name,
        "is_running": sys_manager.road_sim.running
    })

@app.route('/api/control', methods=['POST'])
@requires_auth()
def send_control():
    data = request.get_json() or {}
    action = data.get("action")
    value = data.get("value")
    
    role = request.user.get("role")
    permissions = ROLE_PERMISSIONS.get(role, [])
    
    if action in ["toggle_pause", "change_scenario", "set_speed"]:
        if "system_settings" not in permissions:
            log_audit(request.user["username"], role, "UNAUTHORIZED_ACTION", f"Attempted restricted control: {action}")
            return jsonify({"error": "Forbidden: requires system_settings privileges"}), 403
    elif action == "trigger_test_alert":
        if "submit_reports" not in permissions:
            log_audit(request.user["username"], role, "UNAUTHORIZED_ACTION", f"Attempted restricted control: {action}")
            return jsonify({"error": "Forbidden: requires submit_reports privileges"}), 403

    if sys_manager is None:
        return jsonify({"error": "System not initialized"}), 500

    logger.info(f"Control Triggered by {request.user['username']}: action={action}, value={value}")
    
    if action == "toggle_pause":
        running_state = sys_manager.road_sim.toggle_pause()
        log_audit(request.user["username"], role, "PAUSE_TOGGLE", f"Toggled simulation state. Active={running_state}")
        return jsonify({"status": "success", "running": running_state})
        
    elif action == "change_scenario":
        sys_manager.road_sim.change_scenario(value)
        sys_manager.metrics.reset()
        sys_manager.tracker.tracked_objects.clear()
        log_audit(request.user["username"], role, "SCENARIO_CHANGE", f"Switched road scenario to {value}")
        return jsonify({"status": "success", "scenario": value})
        
    elif action == "set_speed":
        try:
            speed_val = float(value)
            sys_manager.road_sim.set_target_speed(speed_val)
            log_audit(request.user["username"], role, "SPEED_SET", f"Set target velocity to {speed_val} km/h")
            return jsonify({"status": "success", "target_speed": speed_val})
        except ValueError:
            return jsonify({"error": "Invalid speed value"}), 400
            
    elif action == "trigger_test_alert":
        sim = sys_manager.road_sim
        test_distance = sim.current_distance + 12.0
        test_coord, _ = sim._interpolate_position(test_distance)
        
        test_id = len(sim.obstacles) + 1
        test_type = value if value in ["pothole", "speed_bump"] else "pothole"
        
        sim.obstacles.append({
            "id": test_id,
            "type": test_type,
            "distance": test_distance,
            "lateral_offset": 0.0,
            "severity": "high",
            "gps": test_coord,
            "heading": sim.current_heading,
            "detected": False
        })
        
        report_defect(test_type, test_coord[0], test_coord[1], "high", "unresolved", request.user["username"])
        
        log_audit(request.user["username"], role, "INJECT_ANOMALY", f"Injected simulated {test_type} 12m ahead")
        return jsonify({"status": "success", "message": f"Injected '{test_type}' obstacle 12 meters ahead."})
        
    return jsonify({"error": f"Unknown action: {action}"}), 400

# --- PREDICTIVE ANALYTICS API ENDPOINTS ---

@app.route('/api/analytics/hotspots', methods=['GET'])
@requires_auth(permission='view_dashboard')
def get_analytics_hotspots():
    clusterer = HotspotClusterer(eps_meters=50.0, min_samples=5)
    traffic_analyzer = TrafficImpactAnalyzer()
    
    defects = get_defects()
    if sys_manager and hasattr(sys_manager, 'road_sim'):
        for obs in sys_manager.road_sim.obstacles:
            defects.append({
                "latitude": obs["gps"][0],
                "longitude": obs["gps"][1],
                "severity": obs["severity"],
                "type": obs["type"]
            })
            
    cluster_res = clusterer.cluster_defects(defects)
    enriched_hotspots = traffic_analyzer.evaluate_hotspot_traffic(cluster_res["hotspots"])
    
    return jsonify({
        "status": "success",
        "hotspots": enriched_hotspots,
        "noise_count": cluster_res["noise_count"],
        "total_clusters": cluster_res["total_clusters"]
    })

@app.route('/api/analytics/forecast', methods=['GET'])
@requires_auth(permission='view_dashboard')
def get_analytics_forecast():
    predictor = PotholeGrowthPredictor()
    weather_correlator = WeatherCorrelator()
    
    metrics = predictor.evaluate_performance()
    forecast = predictor.predict_growth_30_days(initial_severity=0.42, age_days=14, rain_mm=28.0, freeze_cycles=3, traffic_k_vpd=35.0)
    weather = weather_correlator.compute_weather_correlation(rainfall_mm=28.0, freeze_cycles=3)
    
    return jsonify({
        "status": "success",
        "model_metrics": metrics,
        "forecast_30d": forecast,
        "weather_correlation": weather
    })

@app.route('/api/analytics/routes', methods=['GET'])
@requires_auth(permission='view_dashboard')
def get_analytics_routes():
    clusterer = HotspotClusterer(eps_meters=50.0, min_samples=5)
    risk_scorer = RouteRiskScorer(hotspot_clusterer=clusterer)
    
    defects = get_defects()
    if sys_manager and hasattr(sys_manager, 'road_sim'):
        for obs in sys_manager.road_sim.obstacles:
            defects.append({
                "latitude": obs["gps"][0],
                "longitude": obs["gps"][1],
                "severity": obs["severity"],
                "type": obs["type"]
            })
            
    cluster_res = clusterer.cluster_defects(defects)
    route_points = []
    if sys_manager and hasattr(sys_manager, 'road_sim'):
        route_points = sys_manager.road_sim.route
        
    assessment = risk_scorer.evaluate_route_risk(route_points, hotspots=cluster_res["hotspots"])
    
    return jsonify({
        "status": "success",
        "assessment": assessment
    })

def run_server(host=Config.HOST, port=Config.PORT):
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host=host, port=port, debug=False, threaded=True)
