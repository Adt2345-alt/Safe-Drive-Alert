from flask import Flask, render_template, Response, jsonify, request
from flask_cors import CORS
import cv2
import time
import os
from src.utils.config import Config
from src.utils.logger import LogManager
from src.api.mobile_api import mobile_api_bp, init_mobile_api

from src.core.upload_processor import UploadProcessor

app = Flask(__name__, template_folder="templates")
CORS(app)

# Configure upload directory
UPLOAD_FOLDER = os.path.join(Config.DATA_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Register mobile API blueprint
app.register_blueprint(mobile_api_bp)

logger = LogManager.get_system_logger()
sys_manager = None
active_upload_processor = None

def init_web_server(manager):
    global sys_manager
    sys_manager = manager
    # Initialize mobile API reference as well
    init_mobile_api(manager)

@app.route('/')
def index():
    """
    Renders the main driver alert dashboard UI.
    """
    return render_template('index.html')

def stream_video():
    """
    Video streaming generator function.
    """
    while True:
        if sys_manager is None:
            time.sleep(0.1)
            continue
            
        frame = sys_manager.get_latest_frame()
        if frame is None:
            # Yield empty frame or wait
            time.sleep(0.04)
            continue
            
        # Encode frame as JPEG
        success, encoded_image = cv2.imencode('.jpg', frame)
        if not success:
            time.sleep(0.04)
            continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + encoded_image.tobytes() + b'\r\n')
               
        # Cap streaming FPS around Config.FPS (25Hz -> 40ms interval)
        time.sleep(1.0 / Config.FPS)

@app.route('/video_feed')
def video_feed():
    """
    MJPEG stream of the dashcam camera feed.
    """
    return Response(stream_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- Upload Mode Processing API ---

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
        
        # Match FPS of uploaded video
        time.sleep(1.0 / active_upload_processor.fps)

@app.route('/video_feed_upload')
def video_feed_upload():
    """
    MJPEG stream of the processed uploaded video.
    """
    return Response(stream_upload_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/upload', methods=['POST'])
def upload_video():
    global active_upload_processor
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if file:
        # Clean filename
        safe_filename = "".join([c for c in file.filename if c.isalnum() or c in ['.', '_', '-']]).strip()
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        file.save(file_path)
        logger.info(f"Video uploaded successfully to: {file_path}")
        
        # Stop any active upload processing thread
        if active_upload_processor:
            active_upload_processor.stop()
            
        # Initialize and start new upload processor
        active_upload_processor = UploadProcessor(file_path)
        active_upload_processor.start()
        
        return jsonify({
            "status": "success", 
            "filename": safe_filename,
            "total_frames": active_upload_processor.total_frames
        })

@app.route('/api/upload/status', methods=['GET'])
def upload_status():
    global active_upload_processor
    if active_upload_processor is None:
        return jsonify({"status": "no_upload"})
    return jsonify(active_upload_processor.get_progress())

@app.route('/api/upload/detections', methods=['GET'])
def upload_detections():
    global active_upload_processor
    if active_upload_processor is None:
        return jsonify({"detections": []})
    return jsonify({
        "detections": active_upload_processor.detections_log
    })

@app.route('/api/telemetry', methods=['GET'])
def get_telemetry():
    """
    Exposes complete telemetry data for real-time dashboard updates.
    """
    if sys_manager is None:
        return jsonify({"error": "System not initialized"}), 500
        
    gps_data = sys_manager.gps.get_telemetry()
    active_alert = sys_manager.alert_system.active_alert
    metrics = sys_manager.metrics.get_summary()
    
    # Send all route points and obstacles so map can draw them
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
def send_control():
    """
    Processes actions triggered from dashboard control buttons.
    """
    if sys_manager is None:
        return jsonify({"error": "System not initialized"}), 500
        
    data = request.get_json() or {}
    action = data.get("action")
    value = data.get("value")
    
    logger.info(f"Dashboard Control Triggered: action={action}, value={value}")
    
    if action == "toggle_pause":
        running_state = sys_manager.road_sim.toggle_pause()
        return jsonify({"status": "success", "running": running_state})
        
    elif action == "change_scenario":
        sys_manager.road_sim.change_scenario(value)
        sys_manager.metrics.reset()
        sys_manager.tracker.tracked_objects.clear()
        return jsonify({"status": "success", "scenario": value})
        
    elif action == "set_speed":
        try:
            speed_val = float(value)
            sys_manager.road_sim.set_target_speed(speed_val)
            return jsonify({"status": "success", "target_speed": speed_val})
        except ValueError:
            return jsonify({"error": "Invalid speed value"}), 400
            
    elif action == "trigger_test_alert":
        # Force insert a visual alert directly ahead
        sim = sys_manager.road_sim
        test_distance = sim.current_distance + 12.0 # 12 meters ahead
        test_coord, _ = sim._interpolate_position(test_distance)
        
        test_id = 999
        test_type = value if value in ["pothole", "speed_bump"] else "pothole"
        
        # Inject into simulation obstacles list
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
        
        logger.info(f"Manual Test: Injected dynamic '{test_type}' 12 meters ahead.")
        return jsonify({"status": "success", "message": f"Injected '{test_type}' obstacle 12 meters ahead."})
        
    return jsonify({"error": f"Unknown action: {action}"}), 400

def run_server(host=Config.HOST, port=Config.PORT):
    """
    Runs the Flask application.
    """
    # Disable flask output logging to avoid polluting console, except in debug
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host=host, port=port, debug=False, threaded=True)
