import time
from src.utils.config import Config

class TTCCalculator:
    """
    Time-To-Collision (TTC) Calculator.
    Tracks distance changes to detected hazards across consecutive frames,
    computes relative closing velocity, and calculates Time-To-Collision in seconds.
    Triggers critical warning alert when TTC < 2.0 seconds.
    """
    def __init__(self, critical_ttc_sec=None):
        self.critical_ttc = critical_ttc_sec if critical_ttc_sec else Config.CRITICAL_TTC_THRESHOLD
        self.target_history = {}  # Map target ID -> dict {last_distance, last_time, rel_speed}

    def update_ttc(self, target_id, current_distance_m, current_speed_kmh=40.0, timestamp=None):
        """
        Updates TTC calculation for a given target object ID.
        
        :param target_id: Unique object ID
        :param current_distance_m: Measured absolute distance in meters
        :param current_speed_kmh: Current vehicle telemetry speed in km/h
        :param timestamp: Unix timestamp in seconds
        :return: dict with {ttc_sec, relative_speed_kmh, is_critical_ttc, status}
        """
        if timestamp is None:
            timestamp = time.time()

        # Vehicle ego speed in meters per second (m/s)
        ego_speed_mps = (current_speed_kmh * 1000.0) / 3600.0

        if target_id not in self.target_history:
            self.target_history[target_id] = {
                "last_distance": current_distance_m,
                "last_time": timestamp,
                "rel_speed_mps": ego_speed_mps
            }
            # Initial fallback estimate based on ego vehicle speed
            rel_speed_mps = max(1.0, ego_speed_mps)
        else:
            hist = self.target_history[target_id]
            dt = timestamp - hist["last_time"]
            
            if dt > 0.005 and dt < 1.0:
                dist_change = hist["last_distance"] - current_distance_m
                measured_rel_speed = dist_change / dt
                
                # Smooth relative speed using exponential moving average (alpha = 0.4)
                if measured_rel_speed > 0:
                    rel_speed_mps = 0.4 * measured_rel_speed + 0.6 * hist["rel_speed_mps"]
                else:
                    rel_speed_mps = hist["rel_speed_mps"]
            else:
                rel_speed_mps = hist["rel_speed_mps"]

            # Update history
            hist["last_distance"] = current_distance_m
            hist["last_time"] = timestamp
            hist["rel_speed_mps"] = rel_speed_mps

        # Calculate TTC = Distance / Relative_Speed
        rel_speed_mps = max(0.5, rel_speed_mps)
        ttc_sec = current_distance_m / rel_speed_mps
        ttc_sec = round(min(99.9, max(0.1, ttc_sec)), 1)

        is_critical = ttc_sec <= self.critical_ttc
        is_warning = ttc_sec <= Config.WARNING_TTC_THRESHOLD

        if is_critical:
            status = "CRITICAL_IMPACT_IMMINENT"
        elif is_warning:
            status = "WARNING_APPROACHING"
        else:
            status = "CLEAR"

        return {
            "ttc_sec": ttc_sec,
            "relative_speed_kmh": round((rel_speed_mps * 3600.0) / 1000.0, 1),
            "is_critical_ttc": is_critical,
            "is_warning_ttc": is_warning,
            "status": status
        }

    def clear_target(self, target_id):
        """Clears tracking history for an expired target."""
        if target_id in self.target_history:
            del self.target_history[target_id]
