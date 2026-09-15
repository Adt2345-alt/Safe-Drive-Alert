import time
import threading
import cv2
import sys
import os

# Set python path to base directory to allow direct imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import Config
from src.utils.logger import LogManager
from src.utils.metrics import MetricsTracker
from src.simulation.road_simulator import RoadSimulator
from src.simulation.video_generator import VideoGenerator
from src.core.detector import AIDetector
from src.core.tracker import ObjectTracker
from src.core.gps_simulator import GPSSimulator
from src.core.alert_system import AlertSystem
from src.sensors.imu_reader import IMUReader
from src.sensors.fusion_engine import FusionEngine
from src.perception.depth_estimator import DepthEstimator
from src.perception.distance_calculator import DistanceCalculator
from src.perception.ttc_calculator import TTCCalculator
from src.perception.lane_detector import LaneDetector
from src.api.web_dashboard import init_web_server, run_server

class SystemManager:
    def __init__(self):
        self.logger = LogManager.get_system_logger()
        self.logger.info("Initializing Safe Drive Alert Orchestration...")
        
        # Core Modules
        self.metrics = MetricsTracker()
        self.road_sim = RoadSimulator()
        self.video_gen = VideoGenerator(self.road_sim)
        self.detector = AIDetector()
        self.tracker = ObjectTracker()
        self.gps = GPSSimulator(self.road_sim)
        self.alert_system = AlertSystem(self.metrics)
        
        # Sensor Fusion Modules
        self.imu = IMUReader(spike_threshold=2.5, buffer_capacity=500)
        self.fusion = FusionEngine(history_size=5)
        
        # Perception Suite Modules
        self.depth_estimator = DepthEstimator()
        self.distance_calc = DistanceCalculator()
        self.ttc_calc = TTCCalculator()
        self.lane_detector = LaneDetector(Config.FRAME_WIDTH, Config.FRAME_HEIGHT)
        self.logger.info("Perception Suite (Monocular Depth, Distance Calc, TTC, Lane Detector) online.")
        
        # Frame buffers
        self.latest_frame = None
        self.latest_depth_frame = None
        self.frame_lock = threading.Lock()
        
        # Threads control
        self.thread_running = False
        self.processing_thread = None

    def start(self):
        self.thread_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        self.logger.info("Background processing thread started successfully.")

    def stop(self):
        self.thread_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)
        self.logger.info("Background processing thread stopped.")

    def get_latest_frame(self):
        with self.frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None

    def get_latest_depth_frame(self):
        with self.frame_lock:
            return self.latest_depth_frame.copy() if self.latest_depth_frame is not None else None

    def _processing_loop(self):
        """
        Main processing loop running at target FPS.
        Updates simulator -> samples 100Hz IMU -> runs YOLO camera detector -> estimates monocular depth -> calculates absolute distance & TTC -> checks ego lane -> fuses multi-sensor confidence -> tracks -> alerts.
        """
        target_delay = 1.0 / Config.FPS
        
        while self.thread_running:
            start_time = time.time()
            
            # 1. Update simulation state
            self.road_sim.update()
            
            # 2. Get noisy GPS telemetry
            telemetry = self.gps.get_telemetry()
            
            # Update metrics speed & GPS
            self.metrics.record_speed(telemetry["speed_kmh"])
            self.metrics.record_gps(telemetry["latitude"], telemetry["longitude"])
            
            # 3. Simulate 100Hz IMU sampling with Kalman Filter
            self.imu.simulate_100hz_batch(self.road_sim, dt_sec=target_delay)
            
            # 4. Generate raw 3D perspective camera frame
            raw_frame, visible_obstacles = self.video_gen.generate_frame(self.metrics.fps)
            
            # 5. Estimate relative monocular depth map
            depth_map = self.depth_estimator.estimate_depth_map(raw_frame)
            depth_heatmap = self.depth_estimator.get_depth_heatmap(depth_map)
            
            # 6. Perform visual AI object detection (YOLO)
            cam_detections, inf_time = self.detector.detect(raw_frame, visible_obstacles)
            
            # 7. Apply Perception Suite processing (Distance Calculation, Lane Check, TTC)
            for det in cam_detections:
                # Extract bbox depth median
                depth_med = self.depth_estimator.get_bbox_depth_median(depth_map, det["bbox"])
                
                # Calculate real distance (meters)
                dist_res = self.distance_calc.calculate_distance(det["bbox"], det["class"], depth_med)
                det["distance_m"] = dist_res["distance_m"]
                det["distance_margin_m"] = dist_res["margin_m"]
                
                # Ego Lane Boundary Check
                lane_res = self.lane_detector.is_in_current_lane(det["bbox"], raw_frame)
                det["is_in_lane"] = lane_res["is_in_lane"]
                det["lane_position"] = lane_res["lane_position"]
                
                # Priority boost if in lane
                if lane_res["is_in_lane"]:
                    det["confidence"] = round(min(1.0, det.get("confidence", 0.7) + lane_res["priority_boost"]), 2)
                    
                # Time-to-Collision (TTC) Calculation
                ttc_res = self.ttc_calc.update_ttc(det["id"], det["distance_m"], telemetry["speed_kmh"], timestamp=start_time)
                det["ttc_sec"] = ttc_res["ttc_sec"]
                det["is_critical_ttc"] = ttc_res["is_critical_ttc"]
                det["ttc_status"] = ttc_res["status"]
            
            # 8. Multi-Sensor Fusion Engine (Camera YOLO + IMU Accelerometer + GPS)
            fused_detections = self.fusion.fuse(cam_detections, self.imu, telemetry, frame_timestamp=start_time)
            
            # Preserve perception attributes on fused detections
            for f_det in fused_detections:
                matching_cam = next((cd for cd in cam_detections if cd["id"] == f_det["id"]), None)
                if matching_cam:
                    f_det["distance_m"] = matching_cam.get("distance_m", f_det.get("distance_m", 10.0))
                    f_det["distance_margin_m"] = matching_cam.get("distance_margin_m", 0.5)
                    f_det["is_in_lane"] = matching_cam.get("is_in_lane", True)
                    f_det["lane_position"] = matching_cam.get("lane_position", "YOUR LANE")
                    f_det["ttc_sec"] = matching_cam.get("ttc_sec", 4.0)
                    f_det["is_critical_ttc"] = matching_cam.get("is_critical_ttc", False)
                else:
                    ttc_res = self.ttc_calc.update_ttc(f_det["id"], f_det["distance_m"], telemetry["speed_kmh"], timestamp=start_time)
                    f_det["ttc_sec"] = ttc_res["ttc_sec"]
                    f_det["is_critical_ttc"] = ttc_res["is_critical_ttc"]
                    f_det["is_in_lane"] = True
                    f_det["lane_position"] = "YOUR LANE"
                    f_det["distance_margin_m"] = 0.5

            # 9. Update object tracking state with fused detections
            tracked_objects = self.tracker.update(fused_detections)
            
            # 10. Evaluate and trigger alerts
            self.alert_system.check_alerts(tracked_objects, telemetry)
            
            # 11. Render annotations & lane corridor overlay on frame
            annotated_frame = self._annotate_frame(raw_frame, tracked_objects)
            
            # Save frames to buffers
            with self.frame_lock:
                self.latest_frame = annotated_frame
                self.latest_depth_frame = depth_heatmap
                
            # Update FPS calculation
            self.metrics.update_fps()
            
            # Control frame rate
            elapsed = time.time() - start_time
            sleep_time = target_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _annotate_frame(self, frame, tracked_objects):
        """
        Draws glowing bounding boxes, labels, distance, lane position, TTC, and lane corridor overlay.
        """
        # Render lane corridor overlay
        annotated = self.lane_detector.render_lane_overlay(frame)
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        for obj in tracked_objects:
            xmin, ymin, xmax, ymax = obj.bbox
            
            # Color coding: Red for potholes, Yellow/Orange for speed bumps
            if obj.class_name == "pothole":
                color = (73, 73, 255)       # BGR: Alert Red
                label_color = (0, 0, 255)
            else:
                color = (0, 206, 245)       # BGR: Neon Yellow/Orange
                label_color = (0, 180, 220)
                
            # Make border thicker if it's very close or critical TTC
            thickness = 2
            is_critical_ttc = getattr(obj, "is_critical_ttc", False)
            if obj.distance <= Config.ALERT_TRIGGER_DISTANCE or is_critical_ttc:
                thickness = 3
                cx = (xmin + xmax) // 2
                cy = (ymin + ymax) // 2
                pulse_r = int(12 + 4 * (time.time() * 8 % 3))
                cv2.circle(annotated, (cx, cy), pulse_r, label_color, 1, cv2.LINE_AA)
                
                warn_msg = "IMPACT IMMINENT" if is_critical_ttc else "WARNING"
                cv2.putText(annotated, warn_msg, (xmin, ymin - 25), font, 0.35, label_color, 1, cv2.LINE_AA)
                
            # Draw bounding box
            cv2.rectangle(annotated, (xmin, ymin), (xmax, ymax), color, thickness)
            
            # Build rich label text: e.g. "POTHOLE #10 (8.5m | IN YOUR LANE | TTC: 1.3s)"
            lane_str = getattr(obj, "lane_position", "YOUR LANE")
            ttc_val = getattr(obj, "ttc_sec", 3.0)
            lbl_text = f"{obj.class_name.upper()} #{obj.id} ({obj.distance:.1f}m | {lane_str} | TTC: {ttc_val:.1f}s)"
            
            # Text background rectangle for readability
            text_size = cv2.getTextSize(lbl_text, font, 0.35, 1)[0]
            text_w, text_h = text_size[0], text_size[1]
            
            cv2.rectangle(annotated, 
                          (xmin, ymin - text_h - 10), 
                          (xmin + text_w + 6, ymin), 
                          (15, 20, 30), 
                          -1) # Filled rectangle
            cv2.rectangle(annotated, 
                          (xmin, ymin - text_h - 10), 
                          (xmin + text_w + 6, ymin), 
                          color, 
                          1)
                          
            # Print Label text
            cv2.putText(annotated, lbl_text, (xmin + 3, ymin - 5), font, 0.35, (230, 230, 230), 1, cv2.LINE_AA)
            
        return annotated

if __name__ == "__main__":
    # Instantiate Manager
    manager = SystemManager()
    manager.start()
    
    # Init web server endpoints with manager state
    init_web_server(manager)
    
    try:
        print(f"===========================================================")
        print(f"[*] Safe Drive Alert server starting on http://localhost:{Config.PORT}")
        print(f"===========================================================")
        run_server()
    except KeyboardInterrupt:
        print("\nStopping safe drive alert system gracefully...")
        manager.stop()
        print("System shutdown complete.")
