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
from src.api.web_dashboard import init_web_server, run_server

class SystemManager:
    def __init__(self):
        self.logger = LogManager.get_system_logger()
        self.logger.info("Initializing Safe Drive Alert Orchestration...")
        
        # Modules
        self.metrics = MetricsTracker()
        self.road_sim = RoadSimulator()
        self.video_gen = VideoGenerator(self.road_sim)
        self.detector = AIDetector()
        self.tracker = ObjectTracker()
        self.gps = GPSSimulator(self.road_sim)
        self.alert_system = AlertSystem(self.metrics)
        
        # Frame buffers
        self.latest_frame = None
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

    def _processing_loop(self):
        """
        Main processing loop running at the target FPS.
        Updates simulator -> generates frame -> runs AI -> tracks -> checks alerts -> saves frame.
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
            
            # 3. Generate raw 3D perspective camera frame
            raw_frame, visible_obstacles = self.video_gen.generate_frame(self.metrics.fps)
            
            # 4. Perform simulated object detection
            detections, inf_time = self.detector.detect(raw_frame, visible_obstacles)
            
            # 5. Update object tracking state
            tracked_objects = self.tracker.update(detections)
            
            # 6. Evaluate and trigger alerts
            self.alert_system.check_alerts(tracked_objects, telemetry)
            
            # 7. Render annotations (Bounding Boxes & IDs) on the frame
            annotated_frame = self._annotate_frame(raw_frame, tracked_objects)
            
            # Save frame to buffer
            with self.frame_lock:
                self.latest_frame = annotated_frame
                
            # Update FPS calculation
            self.metrics.update_fps()
            
            # Control frame rate
            elapsed = time.time() - start_time
            sleep_time = target_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _annotate_frame(self, frame, tracked_objects):
        """
        Draws glowing bounding boxes, labels, confidence, and alert circles on the video frame.
        """
        annotated = frame.copy()
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
                
            # Make border thicker if it's very close (alert distance)
            thickness = 2
            if obj.distance <= Config.ALERT_TRIGGER_DISTANCE:
                thickness = 3
                # Draw alert circle indicator around center of bounding box
                cx = (xmin + xmax) // 2
                cy = (ymin + ymax) // 2
                # Pulsing ring effect on warning targets
                pulse_r = int(12 + 4 * (time.time() * 8 % 3))
                cv2.circle(annotated, (cx, cy), pulse_r, label_color, 1, cv2.LINE_AA)
                cv2.putText(annotated, "WARNING", (xmin, ymin - 25), font, 0.35, label_color, 1, cv2.LINE_AA)
                
            # Draw bounding box
            cv2.rectangle(annotated, (xmin, ymin), (xmax, ymax), color, thickness)
            
            # Build label text: e.g. "POTHOLE ID: 3 14.5m"
            lbl_text = f"{obj.class_name.upper()} #{obj.id} ({obj.distance:.1f}m)"
            
            # Text background rectangle for readability
            text_size = cv2.getTextSize(lbl_text, font, 0.38, 1)[0]
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
            cv2.putText(annotated, lbl_text, (xmin + 3, ymin - 5), font, 0.38, (230, 230, 230), 1, cv2.LINE_AA)
            
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
