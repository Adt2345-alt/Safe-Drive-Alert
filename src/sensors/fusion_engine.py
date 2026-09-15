import time
from collections import deque

class FusionEngine:
    """
    Multi-Sensor Fusion Engine for Road Defect Detection.
    Fuses camera (YOLO visual detection), IMU (Z-axis accelerometer impact spikes),
    and GPS telemetry data into an integrated confidence score.
    
    Fusion Rules:
      - Both Camera & IMU detect -> confidence = min(1.0, max(cam, imu) * 1.2)
      - Only Camera detects      -> confidence = cam * 0.8
      - Only IMU detects         -> confidence = imu * 0.6
      - Temporal Consistency     -> Requires detection in >= 3 out of 5 consecutive windows.
    """
    TIME_SYNC_WINDOW_SEC = 0.20  # +/- 200ms alignment window between camera frame & IMU spike
    HISTORY_WINDOW_SIZE = 5

    def __init__(self, history_size=5):
        self.history_size = history_size
        # History window stores recent detections for temporal consistency check
        # List of sets or dicts of detected obstacle IDs per frame
        self.frame_history = deque(maxlen=self.history_size)

    def fuse(self, camera_detections, imu_reader, telemetry, frame_timestamp=None):
        """
        Fuses camera visual detections, IMU accelerometer spikes, and GPS telemetry.
        
        :param camera_detections: List of dicts from AIDetector
        :param imu_reader: IMUReader instance
        :param telemetry: Telemetry dict from GPSSimulator
        :param frame_timestamp: Unix timestamp for camera frame (defaults to time.time())
        :return: List of fused detection objects
        """
        if frame_timestamp is None:
            frame_timestamp = time.time()

        # 1. Query IMU spike events within time sync window of camera frame
        imu_event = imu_reader.get_spike_events(
            time_window_sec=self.TIME_SYNC_WINDOW_SEC, 
            current_time=frame_timestamp
        )

        fused_detections = []
        current_frame_ids = set()

        # Map camera detections by class/id
        camera_potholes = [d for d in camera_detections if d.get("class") == "pothole"]

        # Track which camera detections were matched with IMU
        matched_camera_ids = set()

        # --- BRANCH A: FUSE CAMERA DETECTIONS ---
        for cam_det in camera_detections:
            cam_conf = cam_det.get("confidence", 0.70)
            det_class = cam_det.get("class", "pothole")
            obs_id = cam_det.get("id", 0)

            # Check if this detection is a pothole close to vehicle (< 10m) where physical impact occurs
            is_close_impact_zone = cam_det.get("distance_m", 99.0) <= 12.0

            if det_class == "pothole" and imu_event and is_close_impact_zone:
                # BOTH Camera & IMU Detected!
                imu_conf = imu_event["confidence"]
                fused_conf = min(1.0, max(cam_conf, imu_conf) * 1.2)
                fusion_mode = "BOTH_CAMERA_IMU"
                matched_camera_ids.add(obs_id)
            else:
                # ONLY Camera Detected (or non-pothole visual target)
                fused_conf = cam_conf * 0.8
                fusion_mode = "CAMERA_ONLY"

            current_frame_ids.add(obs_id)

            fused_det = {
                "id": obs_id,
                "class": det_class,
                "confidence": round(fused_conf, 2),
                "camera_confidence": cam_conf,
                "imu_confidence": imu_event["confidence"] if (det_class == "pothole" and imu_event) else 0.0,
                "fusion_mode": fusion_mode,
                "bbox": cam_det.get("bbox", [0, 0, 0, 0]),
                "distance_m": cam_det.get("distance_m", 0.0),
                "severity": cam_det.get("severity", "medium"),
                "latitude": telemetry.get("latitude", 0.0),
                "longitude": telemetry.get("longitude", 0.0),
                "timestamp": frame_timestamp
            }
            fused_detections.append(fused_det)

        # --- BRANCH B: IMU ONLY DETECTION ---
        # If IMU registered a physical impact spike (>2.5g) but camera missed visual line of sight
        if imu_event and not matched_camera_ids:
            # Check if any camera pothole was detected; if not, create an IMU-Only detection
            if not camera_potholes:
                imu_conf = imu_event["confidence"]
                fused_conf = imu_conf * 0.6
                imu_det_id = 9000 + int(frame_timestamp * 10) % 1000

                current_frame_ids.add(imu_det_id)

                fused_det = {
                    "id": imu_det_id,
                    "class": "pothole",
                    "confidence": round(fused_conf, 2),
                    "camera_confidence": 0.0,
                    "imu_confidence": imu_conf,
                    "fusion_mode": "IMU_ONLY",
                    "bbox": [200, 300, 440, 420],  # Estimated central road zone
                    "distance_m": 0.5,             # Under vehicle tires right now
                    "severity": "high" if imu_event["peak_g_raw"] > 3.5 else "medium",
                    "latitude": telemetry.get("latitude", 0.0),
                    "longitude": telemetry.get("longitude", 0.0),
                    "timestamp": frame_timestamp
                }
                fused_detections.append(fused_det)

        # Update temporal consistency frame history
        self.frame_history.append(current_frame_ids)

        # --- TEMPORAL CONSISTENCY CHECK ---
        # Mark detections that appear in at least 3 of the last 5 frame windows
        for det in fused_detections:
            det_id = det["id"]
            hit_count = sum(1 for frame_set in self.frame_history if det_id in frame_set)
            det["temporal_hits"] = hit_count
            det["is_validated"] = hit_count >= 3 or det["fusion_mode"] == "BOTH_CAMERA_IMU"

        return fused_detections
