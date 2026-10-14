import os
import sys
import unittest
import json

# Add workspace root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.api.web_dashboard import app
from backend.api.defects_db import (
    init_defects_db,
    get_vehicles,
    get_vehicle_by_id,
    get_vehicle_routes,
    get_fleet_coverage
)
from scripts.seed_fleet import seed_fleet

class TestFleetFeature(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_defects_db()
        seed_fleet()
        cls.client = app.test_client()
        app.config['TESTING'] = True

    def test_db_get_vehicles(self):
        vehicles = get_vehicles()
        self.assertEqual(len(vehicles), 20)
        active = [v for v in vehicles if v["status"] == "active"]
        offline = [v for v in vehicles if v["status"] == "offline"]
        self.assertEqual(len(active), 15)
        self.assertEqual(len(offline), 5)

    def test_db_get_vehicle_by_id(self):
        vehicle = get_vehicle_by_id("VH-001")
        self.assertIsNotNone(vehicle)
        self.assertEqual(vehicle["id"], "VH-001")
        self.assertIn("driver_name", vehicle)
        self.assertIn("defects", vehicle)
        self.assertIn("route", vehicle)

    def test_db_get_fleet_coverage(self):
        cov = get_fleet_coverage(days=7)
        self.assertEqual(cov["status"], "success")
        self.assertIn("coverage_percentage", cov)
        self.assertIn("corridors", cov)
        self.assertEqual(len(cov["corridors"]), 15)

    def test_api_list_vehicles(self):
        rv = self.client.get('/api/fleet/vehicles')
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["total_count"], 20)
        self.assertEqual(data["active_count"], 15)
        self.assertEqual(data["offline_count"], 5)
        self.assertEqual(len(data["vehicles"]), 20)

    def test_api_vehicle_detail(self):
        rv = self.client.get('/api/fleet/vehicles/VH-005')
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["vehicle"]["id"], "VH-005")

    def test_api_vehicle_detail_not_found(self):
        rv = self.client.get('/api/fleet/vehicles/VH-999')
        self.assertEqual(rv.status_code, 404)
        data = rv.get_json()
        self.assertEqual(data["status"], "error")

    def test_api_live_map(self):
        rv = self.client.get('/api/fleet/live-map')
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["count"], 20)
        self.assertEqual(len(data["vehicles"]), 20)

    def test_api_fleet_coverage(self):
        rv = self.client.get('/api/fleet/coverage?days=7')
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["days"], 7)
        self.assertIn("coverage_percentage", data)
        self.assertGreater(len(data["corridors"]), 0)

if __name__ == '__main__':
    unittest.main()
