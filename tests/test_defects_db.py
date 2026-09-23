import unittest
import os
import sys

# Set python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.defects_db import (
    init_defects_db,
    insert_defect,
    query_defects,
    get_defect_by_id,
    query_nearby_defects,
    DEFECTS_DB_PATH
)

class TestDefectsDB(unittest.TestCase):
    def setUp(self):
        init_defects_db()

    def test_db_file_exists(self):
        self.assertTrue(os.path.exists(DEFECTS_DB_PATH))

    def test_query_defects_returns_list(self):
        defects = query_defects(limit=50)
        self.assertIsInstance(defects, list)
        self.assertGreater(len(defects), 0)
        
        # Check first defect structure
        d = defects[0]
        self.assertIn("id", d)
        self.assertIn("lat", d)
        self.assertIn("lng", d)
        self.assertIn("type", d)
        self.assertIn("severity", d)
        self.assertIn("depth_cm", d)
        self.assertIn("corridor", d)

    def test_insert_live_detection(self):
        new_id = insert_defect(
            latitude=37.7749,
            longitude=-122.4194,
            defect_type="pothole",
            severity="Critical",
            confidence=0.96,
            depth_cm=9.5,
            road_name="Market Street Corridor",
            detection_source="Unit Test Simulation"
        )
        self.assertIsInstance(new_id, int)
        self.assertGreater(new_id, 0)

        # Query back
        defects = query_defects(severity="Critical", limit=10)
        found = any(d["raw_id"] == new_id for d in defects)
        self.assertTrue(found)

    def test_get_defect_by_id(self):
        new_id = insert_defect(
            latitude=37.7699,
            longitude=-122.4668,
            defect_type="pothole",
            severity="High",
            confidence=0.92,
            depth_cm=8.4,
            road_name="Golden Gate Park Route",
            detection_source="Unit Test"
        )
        defect = get_defect_by_id(new_id)
        self.assertIsNotNone(defect)
        self.assertEqual(defect["id"], new_id)
        self.assertEqual(defect["depth_cm"], 8.4)
        self.assertEqual(defect["severity"], "High")

    def test_query_nearby_defects(self):
        new_id = insert_defect(
            latitude=37.7699,
            longitude=-122.4668,
            defect_type="crack",
            severity="Medium",
            confidence=0.88,
            depth_cm=4.2,
            road_name="Golden Gate Park Route",
            detection_source="Unit Test"
        )
        nearby = query_nearby_defects(37.7699, -122.4668, radius_m=50.0)
        self.assertGreater(len(nearby), 0)

    def test_bbox_filtering(self):
        # San Francisco bounding box
        sf_bbox = [-122.45, 37.75, -122.39, 37.81]
        defects = query_defects(bbox=sf_bbox, limit=100)
        for d in defects:
            self.assertTrue(-122.45 <= d["lng"] <= -122.39)
            self.assertTrue(37.75 <= d["lat"] <= 37.81)

if __name__ == '__main__':
    unittest.main()

