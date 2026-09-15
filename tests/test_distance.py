import unittest
import numpy as np
import time

from src.perception.depth_estimator import DepthEstimator
from src.perception.distance_calculator import DistanceCalculator
from src.perception.ttc_calculator import TTCCalculator
from src.perception.lane_detector import LaneDetector

class TestDistanceAndPerception(unittest.TestCase):

    def setUp(self):
        self.depth_estimator = DepthEstimator()
        self.distance_calc = DistanceCalculator(focal_length_px=700.0, camera_height_m=1.4, principal_point_y=240.0)
        self.ttc_calc = TTCCalculator(critical_ttc_sec=2.0)
        self.lane_detector = LaneDetector(frame_width=640, frame_height=480)

    def test_distance_calculator_accuracy(self):
        """Validates distance estimation accuracy within +-10% across test ranges."""
        test_cases = [
            # (bbox [xmin, ymin, xmax, ymax], class_name, depth_median, ground_truth_m)
            ([270, 380, 370, 432], "pothole", 0.85, 5.0),
            ([290, 280, 350, 308], "pothole", 0.60, 12.0),
            ([300, 255, 340, 265], "pothole", 0.35, 25.0),
            ([310, 244, 330, 250], "pothole", 0.20, 40.0)
        ]

        for bbox, cls, depth_med, gt_m in test_cases:
            res = self.distance_calc.calculate_distance(bbox, class_name=cls, depth_map_median=depth_med)
            est_m = res["distance_m"]
            error_pct = abs(est_m - gt_m) / gt_m

            print(f"GT: {gt_m:.1f}m | Est: {est_m:.1f}m (Margin: +-{res['margin_m']}m) | Error: {error_pct*100:.1f}%")

            # Validate accuracy is within +-10% error margin
            self.assertLessEqual(error_pct, 0.10, f"Distance calculation error ({error_pct*100:.1f}%) exceeded 10% tolerance for {gt_m}m ground truth.")

    def test_ttc_calculator_and_critical_trigger(self):
        """Tests TTC calculation and critical warning state when TTC < 2.0s."""
        now = time.time()
        target_id = 42

        # Frame 1: 15.0m distance at t = 0s with speed = 18 km/h (5 m/s -> TTC = 3.0s > 2.0s)
        res1 = self.ttc_calc.update_ttc(target_id, current_distance_m=15.0, current_speed_kmh=18.0, timestamp=now)
        self.assertFalse(res1["is_critical_ttc"])

        # Frame 2: 12.0m distance at t = 0.2s (closing rate = 15m/s = 54 km/h)
        res2 = self.ttc_calc.update_ttc(target_id, current_distance_m=12.0, current_speed_kmh=54.0, timestamp=now + 0.2)
        # TTC = 12.0 / 15.0 = 0.8 seconds (< 2.0s -> CRITICAL!)
        self.assertTrue(res2["is_critical_ttc"], "TTCCalculator failed to trigger critical alert when TTC < 2.0s.")
        self.assertEqual(res2["status"], "CRITICAL_IMPACT_IMMINENT")
        self.assertLessEqual(res2["ttc_sec"], 2.0)

    def test_lane_detector_corridor_check(self):
        """Tests ego-lane assignment ('YOUR LANE' vs side lanes) and priority boost."""
        # Hazard directly in center travel lane [xmin=280, xmax=360] -> center_x = 320
        center_hazard = [280, 300, 360, 400]
        res_center = self.lane_detector.is_in_current_lane(center_hazard)
        self.assertTrue(res_center["is_in_lane"])
        self.assertEqual(res_center["lane_position"], "YOUR LANE")
        self.assertEqual(res_center["priority_boost"], 0.25)

        # Hazard in far left lane [xmin=20, xmax=100] -> center_x = 60
        left_hazard = [20, 300, 100, 400]
        res_left = self.lane_detector.is_in_current_lane(left_hazard)
        self.assertFalse(res_left["is_in_lane"])
        self.assertEqual(res_left["lane_position"], "LEFT LANE")
        self.assertEqual(res_left["priority_boost"], 0.0)

    def test_depth_estimator(self):
        """Tests relative depth map generation and median extraction."""
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        depth_map = self.depth_estimator.estimate_depth_map(dummy_frame)

        self.assertEqual(depth_map.shape, (480, 640))
        self.assertGreaterEqual(np.max(depth_map), 0.5)

        median_depth = self.depth_estimator.get_bbox_depth_median(depth_map, [280, 350, 360, 420])
        self.assertGreater(median_depth, 0.0)

        heatmap = self.depth_estimator.get_depth_heatmap(depth_map)
        self.assertEqual(heatmap.shape, (480, 640, 3))

if __name__ == '__main__':
    unittest.main()
