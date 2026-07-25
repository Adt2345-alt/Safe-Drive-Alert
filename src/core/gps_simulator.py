import random
from src.utils.config import Config

class GPSSimulator:
    def __init__(self, road_simulator):
        self.sim = road_simulator
        self.jitter_std = Config.GPS_JITTER_STD
        
    def get_telemetry(self):
        """
        Returns current GPS coordinates with added jitter, heading, and speed.
        """
        base_lat, base_lon = self.sim.current_coord
        heading = self.sim.current_heading
        speed = self.sim.speed_kmh
        
        # Inject realistic GPS noise (jitter)
        jitter_lat = random.normalvariate(0, self.jitter_std)
        jitter_lon = random.normalvariate(0, self.jitter_std)
        
        noisy_lat = base_lat + jitter_lat
        noisy_lon = base_lon + jitter_lon
        
        return {
            "latitude": round(noisy_lat, 6),
            "longitude": round(noisy_lon, 6),
            "heading": round(heading, 1),
            "speed_kmh": round(speed, 1),
            "raw_lat": base_lat,
            "raw_lon": base_lon
        }
