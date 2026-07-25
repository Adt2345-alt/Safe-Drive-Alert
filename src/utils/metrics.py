import time
import math

class MetricsTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self.start_time = time.time()
        self.frame_times = []
        self.fps = 0.0
        self.total_potholes = 0
        self.total_speed_bumps = 0
        self.distance_traveled = 0.0  # in km
        self.speed_history = []
        self.average_speed = 0.0  # in km/h
        self.last_gps_coord = None
        self.detections_history = [] # list of dicts

    def update_fps(self):
        current_time = time.time()
        self.frame_times.append(current_time)
        # Keep only the last 25 frame times for running average FPS
        if len(self.frame_times) > 25:
            self.frame_times.pop(0)
        
        if len(self.frame_times) > 1:
            duration = self.frame_times[-1] - self.frame_times[0]
            if duration > 0:
                self.fps = len(self.frame_times) / duration
            else:
                self.fps = 0.0
        else:
            self.fps = 0.0

    def record_speed(self, speed_kmh):
        self.speed_history.append(speed_kmh)
        if len(self.speed_history) > 200:
            self.speed_history.pop(0)
        self.average_speed = sum(self.speed_history) / len(self.speed_history)

    def record_gps(self, lat, lon):
        if self.last_gps_coord is not None:
            # Calculate distance using Haversine formula
            lat1, lon1 = self.last_gps_coord
            lat2, lon2 = lat, lon
            
            # Distance in km
            d = self._haversine(lat1, lon1, lat2, lon2)
            self.distance_traveled += d
        
        self.last_gps_coord = (lat, lon)

    def record_detection(self, anomaly_type, lat, lon, severity, obstacle_id):
        if anomaly_type == "pothole":
            self.total_potholes += 1
        elif anomaly_type == "speed_bump":
            self.total_speed_bumps += 1

        self.detections_history.append({
            "id": obstacle_id,
            "type": anomaly_type,
            "latitude": lat,
            "longitude": lon,
            "severity": severity,
            "timestamp": time.time()
        })

    def get_summary(self):
        elapsed = time.time() - self.start_time
        return {
            "uptime_seconds": int(elapsed),
            "fps": round(self.fps, 1),
            "total_potholes": self.total_potholes,
            "total_speed_bumps": self.total_speed_bumps,
            "distance_traveled_km": round(self.distance_traveled, 3),
            "average_speed_kmh": round(self.average_speed, 1),
            "total_detections": self.total_potholes + self.total_speed_bumps
        }

    def _haversine(self, lat1, lon1, lat2, lon2):
        # Radius of the Earth in km
        R = 6371.0
        
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        
        a = math.sin(d_lat / 2) ** 2 + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(d_lon / 2) ** 2
            
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
