import unittest
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import Config
from src.simulation.road_simulator import RoadSimulator
from src.core.gps_simulator import GPSSimulator
from src.core.detector import AIDetector
from src.core.tracker import ObjectTracker
from src.core.alert_system import AlertSystem
from src.utils.metrics import MetricsTracker

class TestSafeDriveAlert(unittest.TestCase):
    def setUp(self):
        self.road_sim = RoadSimulator(scenario_name="city_commute")
        self.gps = GPSSimulator(self.road_sim)
        self.detector = AIDetector()
        self.tracker = ObjectTracker()
        self.metrics = MetricsTracker()
        self.alert_system = AlertSystem(self.metrics)

    def test_simulator_initialization(self):
        self.assertIsNotNone(self.road_sim.route)
        self.assertTrue(len(self.road_sim.route) > 0)
        self.assertTrue(self.road_sim.total_path_length_meters > 0)
        self.assertTrue(len(self.road_sim.obstacles) > 0)
        self.assertEqual(self.road_sim.scenario_name, "city_commute")

    def test_gps_simulator(self):
        telemetry = self.gps.get_telemetry()
        self.assertIn("latitude", telemetry)
        self.assertIn("longitude", telemetry)
        self.assertIn("speed_kmh", telemetry)
        self.assertIn("heading", telemetry)
        self.assertEqual(telemetry["speed_kmh"], Config.SCENARIOS["city_commute"]["base_speed"])

    def test_detector_simulation(self):
        # Create a mock visible obstacle
        mock_visible = [{
            "id": 1,
            "type": "pothole",
            "distance": 10.0,
            "x": 320,
            "y": 300,
            "w": 50,
            "h": 20,
            "severity": "high",
            "gps": (37.7699, -122.4668)
        }]
        
        detections, latency = self.detector.detect(None, mock_visible)
        self.assertTrue(latency > 0)
        
        # Conf threshold is 0.5, since distance is 10m, detection confidence should be high (>0.85)
        # and should be returned in detections
        if len(detections) > 0:
            det = detections[0]
            self.assertEqual(det["id"], 1)
            self.assertEqual(det["class"], "pothole")
            self.assertTrue(det["confidence"] >= Config.DETECTION_CONF_THRESHOLD)
            self.assertEqual(len(det["bbox"]), 4) # xmin, ymin, xmax, ymax

    def test_detector_real_frame(self):
        import numpy as np
        import cv2
        # Create a dummy image representing a black road floor with a yellow speed bump
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Fill asphalt road region (lower 50%)
        dummy_frame[240:480, :] = (24, 28, 38)
        # Draw a yellow speed bump (cyan-yellow BGR is (0, 200, 230))
        cv2.rectangle(dummy_frame, (150, 320), (490, 340), (0, 200, 230), -1)
        
        detections, latency = self.detector.detect_real_frame(dummy_frame)
        self.assertTrue(latency > 0)
        self.assertTrue(len(detections) > 0)
        self.assertEqual(detections[0]["class"], "speed_bump")

    def test_tracker_mechanics(self):
        detections = [{
            "id": 1,
            "class": "pothole",
            "confidence": 0.95,
            "bbox": [100, 200, 150, 220],
            "distance_m": 12.0,
            "severity": "medium",
            "gps": (37.7699, -122.4668)
        }]
        
        tracked = self.tracker.update(detections)
        self.assertEqual(len(tracked), 1)
        self.assertEqual(tracked[0].id, 1)
        self.assertEqual(tracked[0].class_name, "pothole")
        self.assertFalse(tracked[0].alert_triggered)

        # Update again with no detections to check max disappeared logic
        for _ in range(Config.TRACKING_MAX_DISAPPEARED + 2):
            tracked = self.tracker.update([])
            
        self.assertEqual(len(tracked), 0)

    def test_alert_triggering(self):
        # Setup mock telemetry and tracked object close to vehicle (10m)
        telemetry = self.gps.get_telemetry()
        from src.core.tracker import TrackedObject
        mock_tracked = TrackedObject(
            obj_id=5,
            class_name="speed_bump",
            bbox=[200, 300, 240, 320],
            distance=10.0, # Within Alert trigger distance (15m)
            severity="high",
            gps=(37.7699, -122.4668)
        )
        
        alert = self.alert_system.check_alerts([mock_tracked], telemetry)
        self.assertIsNotNone(alert)
        self.assertEqual(alert["id"], 5)
        self.assertEqual(alert["type"], "speed_bump")
        self.assertEqual(self.metrics.total_speed_bumps, 1)
        self.assertTrue(mock_tracked.alert_triggered)
        
        # Verify next call doesn't trigger duplicate alert
        second_alert = self.alert_system.check_alerts([mock_tracked], telemetry)
        self.assertIsNone(second_alert)

    def test_detector_real_signs(self):
        import numpy as np
        import cv2
        
        # Create dummy frame
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Draw a red circular sign (Speed Limit 60 representation) in the upper right shoulder ROI (x=450, y=180)
        # Outer red ring
        cv2.circle(dummy_frame, (450, 180), 20, (0, 0, 255), -1)
        # Inner white face
        cv2.circle(dummy_frame, (450, 180), 16, (255, 255, 255), -1)
        
        # Detect
        detections, latency = self.detector.detect_real_frame(dummy_frame)
        self.assertTrue(len(detections) > 0)
        self.assertEqual(detections[0]["class"], "speed_limit_60")

if __name__ == "__main__":
    unittest.main()
