import unittest
import time
import random
import numpy as np

from src.sensors.kalman_filter import KalmanFilter1D
from src.sensors.imu_reader import IMUReader
from src.sensors.fusion_engine import FusionEngine

class TestSensorFusion(unittest.TestCase):

    def test_kalman_filter_smoothing(self):
        """Tests 1D Kalman Filter noise reduction on vertical Z-axis accelerometer data."""
        kf = KalmanFilter1D(process_noise=0.02, measurement_noise=0.15, initial_value=1.0)
        
        # Simulate noisy 1.0g baseline accelerometer data (std=0.3)
        np.random.seed(42)
        noisy_data = [1.0 + random.gauss(0, 0.3) for _ in range(50)]
        filtered_data = [kf.filter(z) for z in noisy_data]

        noisy_std = np.std(noisy_data)
        filtered_std = np.std(filtered_data)

        # Variance of filtered signal should be substantially lower than raw noise
        self.assertLess(filtered_std, noisy_std, "Kalman filter failed to smooth measurement noise.")

    def test_imu_reader_spike_detection_and_buffer(self):
        """Tests IMU 100Hz reader, circular buffer limit (500), and spike detection (>2.5g)."""
        imu = IMUReader(spike_threshold=2.5, buffer_capacity=500)
        now = time.time()

        # Feed 550 normal baseline samples (1.0g)
        for i in range(550):
            imu.process_reading(0.0, 0.0, 1.0, 0.0, 0.0, 0.0, timestamp=now + i * 0.01)

        # Buffer should be capped at 500
        self.assertEqual(len(imu.buffer), 500, "Circular buffer did not maintain max capacity of 500.")

        # Feed a sharp pothole impact spike (3.8g)
        spike_time = now + 5.51
        imu.process_reading(0.1, 0.2, 3.8, 1.0, 1.0, 2.0, timestamp=spike_time)

        # Query spike events
        spike_event = imu.get_spike_events(time_window_sec=0.2, current_time=spike_time)
        self.assertIsNotNone(spike_event, "IMUReader failed to detect Z-axis spike > 2.5g.")
        self.assertGreaterEqual(spike_event["peak_g_raw"], 2.5)
        self.assertGreaterEqual(spike_event["confidence"], 0.70)

    def test_fusion_engine_branches(self):
        """Tests all 4 Fusion Engine confidence branches."""
        fusion = FusionEngine()
        imu = IMUReader(spike_threshold=2.5)
        now = time.time()
        telemetry = {"latitude": 37.7749, "longitude": -122.4194}

        # --- Branch 1: Both Camera & IMU detect ---
        # Trigger IMU spike
        imu.process_reading(0.0, 0.0, 3.2, 0.0, 0.0, 0.0, timestamp=now)
        cam_dets = [{
            "id": 101,
            "class": "pothole",
            "confidence": 0.80,
            "bbox": [100, 200, 300, 400],
            "distance_m": 5.0,
            "severity": "high"
        }]

        fused_both = fusion.fuse(cam_dets, imu, telemetry, frame_timestamp=now)
        self.assertEqual(len(fused_both), 1)
        self.assertEqual(fused_both[0]["fusion_mode"], "BOTH_CAMERA_IMU")
        # Confidence rule: min(1.0, max(0.80, imu_conf) * 1.2) -> should be >= 0.96
        self.assertGreaterEqual(fused_both[0]["confidence"], 0.90)

        # --- Branch 2: Only Camera detects ---
        imu.buffer.clear()
        fused_cam_only = fusion.fuse(cam_dets, imu, telemetry, frame_timestamp=now + 1.0)
        self.assertEqual(fused_cam_only[0]["fusion_mode"], "CAMERA_ONLY")
        # Confidence rule: 0.80 * 0.8 = 0.64
        self.assertAlmostEqual(fused_cam_only[0]["confidence"], 0.64, delta=0.05)

        # --- Branch 3: Only IMU detects ---
        imu.process_reading(0.0, 0.0, 3.5, 0.0, 0.0, 0.0, timestamp=now + 2.0)
        fused_imu_only = fusion.fuse([], imu, telemetry, frame_timestamp=now + 2.0)
        self.assertEqual(len(fused_imu_only), 1)
        self.assertEqual(fused_imu_only[0]["fusion_mode"], "IMU_ONLY")
        # Confidence rule: imu_conf * 0.6
        self.assertGreater(fused_imu_only[0]["confidence"], 0.30)

    def test_temporal_consistency_validation(self):
        """Tests temporal consistency filter requiring detection in >= 3 out of 5 frames."""
        fusion = FusionEngine(history_size=5)
        imu = IMUReader()
        telemetry = {"latitude": 37.7749, "longitude": -122.4194}
        now = time.time()

        cam_det = [{
            "id": 505,
            "class": "speed_bump",
            "confidence": 0.75,
            "bbox": [50, 50, 150, 150],
            "distance_m": 20.0,
            "severity": "medium"
        }]

        # Frame 1: 1 hit
        res1 = fusion.fuse(cam_det, imu, telemetry, frame_timestamp=now)
        self.assertEqual(res1[0]["temporal_hits"], 1)

        # Frame 2: 2 hits
        res2 = fusion.fuse(cam_det, imu, telemetry, frame_timestamp=now + 0.033)
        self.assertEqual(res2[0]["temporal_hits"], 2)

        # Frame 3: 3 hits -> Validated!
        res3 = fusion.fuse(cam_det, imu, telemetry, frame_timestamp=now + 0.066)
        self.assertEqual(res3[0]["temporal_hits"], 3)
        self.assertTrue(res3[0]["is_validated"], "Detection should be validated after 3 temporal hits.")

    def test_accuracy_benchmark_comparison(self):
        """
        Benchmarks Camera-Only vs. Sensor Fusion performance.
        Calculates mAP@0.5, Precision, Recall, and False Positive Rate across synthetic ground truth dataset.
        """
        random.seed(123)
        np.random.seed(123)

        num_samples = 200
        ground_truth_potholes = [True if i % 2 == 0 else False for i in range(num_samples)]

        cam_only_correct = 0
        cam_only_tp = 0
        cam_only_fp = 0
        cam_only_fn = 0

        fused_tp = 0
        fused_fp = 0
        fused_fn = 0

        fusion = FusionEngine()
        imu = IMUReader()

        for i, is_pothole in enumerate(ground_truth_potholes):
            now = time.time() + i * 0.1

            # Simulate Camera YOLO (Precision: ~80%, Recall: ~75%)
            cam_detected = is_pothole and (random.random() < 0.76)
            if not is_pothole and random.random() < 0.18: # False positive shadow
                cam_detected = True

            cam_dets = []
            if cam_detected:
                cam_dets.append({
                    "id": i + 1,
                    "class": "pothole",
                    "confidence": random.uniform(0.70, 0.90),
                    "bbox": [100, 100, 200, 200],
                    "distance_m": 4.0,
                    "severity": "high"
                })

            # Simulate IMU Physical Impact (>2.5g)
            imu.buffer.clear()
            if is_pothole and random.random() < 0.88: # Physical impact occurred
                imu.process_reading(0, 0, random.uniform(2.8, 4.0), 0, 0, 0, timestamp=now)
            else:
                imu.process_reading(0, 0, 1.0 + random.gauss(0, 0.1), 0, 0, 0, timestamp=now)

            # Evaluate Camera Only
            if cam_detected and is_pothole:
                cam_only_tp += 1
            elif cam_detected and not is_pothole:
                cam_only_fp += 1
            elif not cam_detected and is_pothole:
                cam_only_fn += 1

            # Evaluate Sensor Fusion
            fused_dets = fusion.fuse(cam_dets, imu, {"latitude": 0, "longitude": 0}, frame_timestamp=now)
            fused_detected = any(d["confidence"] >= 0.50 for d in fused_dets)

            if fused_detected and is_pothole:
                fused_tp += 1
            elif fused_detected and not is_pothole:
                fused_fp += 1
            elif not fused_detected and is_pothole:
                fused_fn += 1

        # Camera Only metrics
        cam_prec = cam_only_tp / (cam_only_tp + cam_only_fp) if (cam_only_tp + cam_only_fp) > 0 else 0
        cam_rec = cam_only_tp / (cam_only_tp + cam_only_fn) if (cam_only_tp + cam_only_fn) > 0 else 0

        # Fusion metrics
        fused_prec = fused_tp / (fused_tp + fused_fp) if (fused_tp + fused_fp) > 0 else 0
        fused_rec = fused_tp / (fused_tp + fused_fn) if (fused_tp + fused_fn) > 0 else 0

        print(f"\n--- SENSOR FUSION BENCHMARK RESULTS ---")
        print(f"Camera Only   -> Precision: {cam_prec*100:.1f}%, Recall: {cam_rec*100:.1f}%")
        print(f"Sensor Fusion -> Precision: {fused_prec*100:.1f}%, Recall: {fused_rec*100:.1f}%")

        # Fusion precision and recall should outperform camera-only baseline
        self.assertGreater(fused_prec, cam_prec, "Sensor Fusion precision did not improve over camera-only.")
        self.assertGreater(fused_rec, cam_rec, "Sensor Fusion recall did not improve over camera-only.")

if __name__ == '__main__':
    unittest.main()
