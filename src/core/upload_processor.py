import cv2
import time
import threading
import os
from src.utils.config import Config
from src.utils.logger import LogManager
from src.core.detector import AIDetector
from src.core.tracker import ObjectTracker

class UploadProcessor:
    def __init__(self, video_path):
        self.logger = LogManager.get_system_logger()
        self.video_path = video_path
        self.filename = os.path.basename(video_path)
        
        # Detector & Tracker instances
        self.detector = AIDetector()
        self.tracker = ObjectTracker()
        
        # Playback & state control
        self.running = False
        self.status = "idle"  # idle, processing, completed, stopped, error
        self.current_frame_idx = 0
        self.total_frames = 0
        self.fps = Config.FPS
        
        # Frame buffering
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        
        # Log of detected anomalies
        self.detections_log = []
        self.thread = None
        
        self._get_video_info()

    def _get_video_info(self):
        try:
            cap = cv2.VideoCapture(self.video_path)
            if cap.isOpened():
                self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                video_fps = cap.get(cv2.CAP_PROP_FPS)
                if video_fps > 0:
                    self.fps = video_fps
            cap.release()
        except Exception as e:
            self.logger.error(f"Failed to query video info for {self.filename}: {e}")

    def start(self):
        if self.running:
            return
        self.running = True
        self.status = "processing"
        self.thread = threading.Thread(target=self._run_pipeline, daemon=True)
        self.thread.start()
        self.logger.info(f"Asynchronous upload processing thread started for video: {self.filename}")

    def stop(self):
        self.running = False
        self.status = "stopped"
        if self.thread:
            self.thread.join(timeout=2.0)
        self.logger.info(f"Stopped upload processing for video: {self.filename}")

    def get_latest_frame(self):
        with self.frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None

    def get_progress(self):
        pct = 0
        if self.total_frames > 0:
            pct = int((self.current_frame_idx / self.total_frames) * 100)
        return {
            "filename": self.filename,
            "status": self.status,
            "current_frame": self.current_frame_idx,
            "total_frames": self.total_frames,
            "percent": pct,
            "detections_count": len(self.detections_log)
        }

    def _run_pipeline(self):
        try:
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                self.status = "error"
                self.logger.error(f"Could not open uploaded video file: {self.video_path}")
                return
                
            self.current_frame_idx = 0
            # Target delay to simulate original video speed
            frame_delay = 1.0 / self.fps if self.fps > 0 else 0.04
            
            while self.running:
                start_time = time.time()
                
                ret, frame = cap.read()
                if not ret:
                    # End of video file reached
                    self.status = "completed"
                    self.logger.info(f"Completed processing uploaded video file: {self.filename}")
                    break
                    
                self.current_frame_idx += 1
                
                # Resize to standard size to ensure consistent aspect ratios for detector
                frame_resized = cv2.resize(frame, (Config.FRAME_WIDTH, Config.FRAME_HEIGHT))
                
                # Run pixel-based detector
                detections, inf_time = self.detector.detect_real_frame(frame_resized)
                
                # Update tracker
                tracked_objects = self.tracker.update(detections)
                
                # Log any newly alert-triggered defects in our detections_log list
                timestamp_s = round(self.current_frame_idx / self.fps, 2)
                for obj in tracked_objects:
                    # Let's check distance to trigger alerts (e.g. 15 meters)
                    # We can use a cooldown based on tracker ID to log once
                    is_new = True
                    for logged in self.detections_log:
                        if logged["id"] == obj.id:
                            is_new = False
                            break
                            
                    if is_new and obj.distance <= Config.ALERT_TRIGGER_DISTANCE:
                        self.detections_log.append({
                            "id": obj.id,
                            "type": obj.class_name,
                            "timestamp_seconds": timestamp_s,
                            "severity": obj.severity,
                            "distance_m": obj.distance
                        })
                        self.logger.info(f"Video Upload Anomaly: Detected {obj.class_name.upper()} at {timestamp_s}s (distance: {obj.distance}m)")
                        try:
                            from backend.api.defects_db import insert_defect
                            insert_defect(
                                latitude=getattr(obj, 'gps', (12.9716, 77.5946))[0] or 12.9716,
                                longitude=getattr(obj, 'gps', (12.9716, 77.5946))[1] or 77.5946,
                                defect_type="pothole" if obj.class_name == "pothole" else ("speedbump" if obj.class_name == "speed_bump" else "crack"),
                                severity=obj.severity if obj.severity in ["Critical", "High", "Medium", "Low"] else "High",
                                confidence=getattr(obj, 'confidence', 0.92),
                                depth_cm=getattr(obj, 'depth_cm', 7.2),
                                road_name="Outer Ring Road Arterial",
                                detection_source="Road Video Analyzer"
                            )

                        except Exception as ex:
                            self.logger.warning(f"Failed to record upload detection to defects.db: {ex}")

                # Annotate frame
                annotated = self._annotate_frame(frame_resized, tracked_objects, timestamp_s)
                
                # Update buffer
                with self.frame_lock:
                    self.latest_frame = annotated
                    
                # Regulate playback speed to real-time FPS
                elapsed = time.time() - start_time
                sleep_time = frame_delay - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            cap.release()
        except Exception as e:
            self.status = "error"
            self.logger.error(f"Error processing video upload file: {e}")
            
    def _annotate_frame(self, frame, tracked_objects, timestamp_s):
        annotated = frame.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Draw bounding boxes and labels
        for obj in tracked_objects:
            xmin, ymin, xmax, ymax = obj.bbox
            
            # Color coding: Red for potholes, Yellow for speed bumps
            color = (73, 73, 255) if obj.class_name == "pothole" else (0, 206, 245)
            thickness = 2
            
            # Highlight warning if close
            if obj.distance <= Config.ALERT_TRIGGER_DISTANCE:
                thickness = 3
                # Flash red HUD border around the entire canvas to indicate extreme threat!
                cv2.rectangle(annotated, (0, 0), (Config.FRAME_WIDTH, Config.FRAME_HEIGHT), (73, 73, 255), 4)
                
            # Draw bbox
            cv2.rectangle(annotated, (xmin, ymin), (xmax, ymax), color, thickness)
            
            # Label
            lbl = f"{obj.class_name.upper()} #{obj.id} ({obj.distance:.1f}m)"
            cv2.putText(annotated, lbl, (xmin, ymin - 6), font, 0.4, color, 1, cv2.LINE_AA)
            
        # Draw HUD overlays indicating "ANALYSIS MODE" and elapsed time
        cv2.rectangle(annotated, (10, 10), (220, 45), (15, 20, 30), -1)
        cv2.rectangle(annotated, (10, 10), (220, 45), (0, 242, 254), 1)
        cv2.putText(annotated, "ANALYSIS: VIDEO UPLOAD", (20, 26), font, 0.35, (0, 242, 254), 1, cv2.LINE_AA)
        cv2.putText(annotated, f"TIME: {timestamp_s:.2f}s | FRAME: {self.current_frame_idx}", (20, 38), font, 0.35, (180, 180, 180), 1, cv2.LINE_AA)
        
        # Warn if alert is active
        active_warnings = [o for o in tracked_objects if o.distance <= Config.ALERT_TRIGGER_DISTANCE]
        if active_warnings:
            warn = active_warnings[0]
            w_text = f"WARNING: {warn.class_name.upper()} DETECTED AHEAD!"
            cv2.rectangle(annotated, (Config.FRAME_WIDTH//2 - 160, Config.FRAME_HEIGHT - 45), 
                          (Config.FRAME_WIDTH//2 + 160, Config.FRAME_HEIGHT - 15), (15, 20, 30), -1)
            cv2.rectangle(annotated, (Config.FRAME_WIDTH//2 - 160, Config.FRAME_HEIGHT - 45), 
                          (Config.FRAME_WIDTH//2 + 160, Config.FRAME_HEIGHT - 15), (73, 73, 255), 1)
            cv2.putText(annotated, w_text, (Config.FRAME_WIDTH//2 - 145, Config.FRAME_HEIGHT - 25), font, 0.4, (73, 73, 255), 1, cv2.LINE_AA)
            
        return annotated
