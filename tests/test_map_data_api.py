import unittest
import json
import sys
import os

# Set python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.web_dashboard import app

class TestMapDataAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_get_defects(self):
        response = self.app.get('/api/map/defects?limit=50')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertIn("defects", data)

    def test_get_defects_filtering(self):
        response = self.app.get('/api/map/defects?severity=Critical&type=pothole&limit=20')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")

    def test_get_heatmap(self):
        response = self.app.get('/api/map/heatmap')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertIn("points", data)

    def test_get_trajectory(self):
        response = self.app.get('/api/map/trajectory')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertIn("path", data)

    def test_get_predictions(self):
        response = self.app.get('/api/map/predictions')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertIn("predictions", data)

    def test_get_work_orders(self):
        response = self.app.get('/api/map/municipality/work-orders')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertIn("features", data)

    def test_get_defect_detail(self):
        # Insert test defect first
        from backend.api.defects_db import insert_defect
        defect_id = insert_defect(
            latitude=37.7699,
            longitude=-122.4668,
            defect_type="pothole",
            severity="High",
            depth_cm=7.5,
            road_name="API Test Road"
        )
        response = self.app.get(f'/api/defects/{defect_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["id"], defect_id)
        self.assertEqual(data["depth_cm"], 7.5)
        self.assertEqual(data["type"], "pothole")

    def test_get_defect_detail_404(self):
        response = self.app.get('/api/defects/99999999')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "error")

if __name__ == '__main__':
    unittest.main()

