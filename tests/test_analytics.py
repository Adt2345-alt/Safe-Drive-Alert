import unittest
import os
import numpy as np

from src.analytics.clustering import HotspotClusterer
from src.analytics.prediction import PotholeGrowthPredictor
from src.analytics.weather_integration import WeatherCorrelator
from src.analytics.traffic_integration import TrafficImpactAnalyzer
from src.analytics.risk_scorer import RouteRiskScorer

class TestPredictiveAnalytics(unittest.TestCase):

    def setUp(self):
        self.clusterer = HotspotClusterer(eps_meters=50.0, min_samples=5)
        self.predictor = PotholeGrowthPredictor()
        self.weather_correlator = WeatherCorrelator()
        self.traffic_analyzer = TrafficImpactAnalyzer()
        self.risk_scorer = RouteRiskScorer(hotspot_clusterer=self.clusterer)

    def test_hotspot_clustering_dbscan(self):
        """Tests DBSCAN hotspot clustering on GPS coordinates with eps=50m and min_samples=5."""
        # Generate 6 defect points closely clustered near (37.7749, -122.4194) within ~20m
        base_lat, base_lon = 37.7749, -122.4194
        cluster_defects = [
            {"latitude": base_lat + (i * 0.00005), "longitude": base_lon + (i * 0.00005), "severity": "high", "type": "pothole"}
            for i in range(6)
        ]
        # Add 2 outlier noise points far away
        noise_defects = [
            {"latitude": 37.8000, "longitude": -122.5000, "severity": "medium", "type": "pothole"},
            {"latitude": 37.8100, "longitude": -122.5100, "severity": "low", "type": "speed_bump"}
        ]
        all_defects = cluster_defects + noise_defects

        res = self.clusterer.cluster_defects(all_defects)
        self.assertIn("hotspots", res)
        self.assertIn("total_clusters", res)
        self.assertGreaterEqual(res["total_clusters"], 1)

        first_hotspot = res["hotspots"][0]
        self.assertIn("hotspot_id", first_hotspot)
        self.assertIn("latitude", first_hotspot)
        self.assertIn("longitude", first_hotspot)
        self.assertIn("risk_level", first_hotspot)
        self.assertGreaterEqual(first_hotspot["defect_count"], 5)

    def test_pothole_growth_prediction_and_metrics(self):
        """Tests 30-day pothole degradation trajectory forecasting and validation metrics (MAE, RMSE, R2)."""
        metrics = self.predictor.evaluate_performance()
        self.assertIn("MAE", metrics)
        self.assertIn("RMSE", metrics)
        self.assertIn("R2_Score", metrics)
        self.assertLess(metrics["MAE"], 0.10)
        self.assertGreater(metrics["R2_Score"], 0.85)

        # Predict growth for a sample pothole over 30 days
        forecast = self.predictor.predict_growth_30_days(initial_severity=0.45, age_days=15, rain_mm=25.0, freeze_cycles=2, traffic_k_vpd=30.0)
        self.assertIn("days_until_critical", forecast)
        self.assertIn("daily_forecast", forecast)
        self.assertEqual(len(forecast["daily_forecast"]), 30)
        self.assertIn("status_message", forecast)
        self.assertIn("Will become critical in", forecast["status_message"])

    def test_weather_correlation_engine(self):
        """Tests OpenWeatherMap weather telemetry and rainfall/freeze-thaw correlation formulation."""
        weather = self.weather_correlator.get_current_weather()
        self.assertIn("temp_c", weather)
        self.assertIn("humidity", weather)
        self.assertIn("rain_3h", weather)

        correlation = self.weather_correlator.compute_weather_correlation(rainfall_mm=30.0, freeze_cycles=4)
        self.assertIn("percentage_increase", correlation)
        self.assertIn("formation_multiplier", correlation)
        self.assertIn("statement", correlation)
        self.assertGreaterEqual(correlation["percentage_increase"], 120)
        self.assertIn("Rain & freeze activity increases pothole formation by", correlation["statement"])

    def test_traffic_impact_analyzer_priority_scoring(self):
        """Tests traffic volume calculation and municipal P1-P3 priority dispatch scores."""
        score_res = self.traffic_analyzer.compute_priority_score(vehicles_per_day=45000, severity_str="high", growth_rate_daily=0.04)
        self.assertIn("priority_score", score_res)
        self.assertIn("priority_rank", score_res)
        self.assertIn("dispatch_urgency", score_res)
        self.assertGreaterEqual(score_res["priority_score"], 70.0)
        self.assertEqual(score_res["priority_rank"], "P1_URGENT")

        # Low traffic test
        low_res = self.traffic_analyzer.compute_priority_score(vehicles_per_day=5000, severity_str="low", growth_rate_daily=0.01)
        self.assertLess(low_res["priority_score"], 50.0)

    def test_route_risk_scorer_and_bypass(self):
        """Tests route safety risk scoring (0-100) and safer alternative route recommendations."""
        hotspots = [
            {"hotspot_id": 1, "latitude": 37.7749, "longitude": -122.4194, "density_score": 150.0, "radius_meters": 100.0}
        ]
        route_through_hotspot = [
            [37.7700, -122.4194],
            [37.7749, -122.4194],
            [37.7800, -122.4194]
        ]
        res = self.risk_scorer.evaluate_route_risk(route_through_hotspot, hotspots=hotspots)
        self.assertIn("route_risk_score", res)
        self.assertIn("risk_level", res)
        self.assertIn("safer_alternative", res)
        self.assertGreater(res["route_risk_score"], 10.0)
        self.assertIn("risk_reduction_pct", res["safer_alternative"])

if __name__ == '__main__':
    unittest.main()
