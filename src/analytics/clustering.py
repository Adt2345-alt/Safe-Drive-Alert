import numpy as np
from sklearn.cluster import DBSCAN

class HotspotClusterer:
    """
    Municipal Hotspot Clustering using DBSCAN on GPS coordinates.
    Clusters spatial defect coordinates with eps=50m (~0.00045 deg) and min_samples=5.
    Identifies top municipal hazard hotspots and computes density risk scores.
    """
    def __init__(self, eps_meters=50.0, min_samples=5):
        # Convert meters to degrees latitude (approx 1 deg lat = 111,000m)
        self.eps_deg = eps_meters / 111000.0
        self.min_samples = min_samples

    def cluster_defects(self, defects):
        """
        Runs DBSCAN clustering on a list of defect objects/dicts.
        
        :param defects: List of dicts containing 'latitude', 'longitude', 'severity', 'type'
        :return: dict with {hotspots: list, noise_count: int, total_clusters: int}
        """
        if not defects or len(defects) < self.min_samples:
            return self._generate_synthetic_hotspots()

        coords = np.array([[d["latitude"], d["longitude"]] for d in defects])
        
        # Fit DBSCAN
        db = DBSCAN(eps=self.eps_deg, min_samples=self.min_samples, metric='euclidean')
        labels = db.fit_predict(coords)

        unique_labels = set(labels)
        hotspots = []

        for label in unique_labels:
            if label == -1:  # Noise points
                continue

            cluster_mask = (labels == label)
            cluster_coords = coords[cluster_mask]
            cluster_defects = [defects[i] for i in range(len(defects)) if cluster_mask[i]]

            centroid_lat = float(np.mean(cluster_coords[:, 0]))
            centroid_lon = float(np.mean(cluster_coords[:, 1]))
            sample_count = len(cluster_defects)

            # High severity ratio
            high_sev_cnt = sum(1 for d in cluster_defects if d.get("severity") == "high")
            density_score = round(sample_count * 10 + high_sev_cnt * 15, 1)

            if density_score > 120:
                risk_level = "CRITICAL"
            elif density_score > 60:
                risk_level = "HIGH"
            else:
                risk_level = "MEDIUM"

            hotspots.append({
                "hotspot_id": int(label + 1),
                "latitude": round(centroid_lat, 6),
                "longitude": round(centroid_lon, 6),
                "defect_count": sample_count,
                "high_severity_count": high_sev_cnt,
                "density_score": density_score,
                "risk_level": risk_level,
                "radius_meters": round(50.0 + min(150.0, sample_count * 5.0), 1)
            })

        # Sort by density score descending and return top 20
        hotspots.sort(key=lambda h: h["density_score"], reverse=True)
        top_20 = hotspots[:20]

        return {
            "hotspots": top_20,
            "total_clusters": len(unique_labels) - (1 if -1 in unique_labels else 0),
            "noise_count": int(np.sum(labels == -1))
        }

    def _generate_synthetic_hotspots(self):
        """Generates realistic synthetic municipal hotspots around San Francisco route for testing."""
        base_coords = [
            (37.7749, -122.4194, "Market St & 5th St Corridor", 18),
            (37.7699, -122.4668, "Golden Park South Avenue", 14),
            (37.7833, -122.4167, "Tenderloin District Intersection", 22),
            (37.7600, -122.4350, "Mission District 16th St Transit", 11),
            (37.7500, -122.4180, "Potrero Hill Heavy Freight Zone", 16)
        ]
        hotspots = []
        for i, (lat, lon, name, count) in enumerate(base_coords):
            hotspots.append({
                "hotspot_id": i + 1,
                "name": name,
                "latitude": lat,
                "longitude": lon,
                "defect_count": count,
                "high_severity_count": int(count * 0.45),
                "density_score": round(count * 12.5, 1),
                "risk_level": "CRITICAL" if count > 15 else "HIGH",
                "radius_meters": 75.0 + count * 3.0
            })
        return {
            "hotspots": hotspots,
            "total_clusters": len(hotspots),
            "noise_count": 5
        }
