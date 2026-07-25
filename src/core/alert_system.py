import time
import threading
import sys
from src.utils.config import Config
from src.utils.logger import LogManager

# Windows-specific winsound import
if sys.platform == "win32":
    import winsound
else:
    winsound = None

class AlertSystem:
    def __init__(self, metrics_tracker):
        self.logger = LogManager.get_system_logger()
        self.metrics = metrics_tracker
        self.trigger_distance = Config.ALERT_TRIGGER_DISTANCE
        
        # Keep track of active alerts for API consumption
        self.active_alert = None
        self.last_alert_time = 0.0
        self.cooldown = Config.COOLDOWN_PERIOD_SECONDS
        
    def check_alerts(self, tracked_objects, current_telemetry):
        """
        Scans tracked objects to see if any are within the critical distance
        and haven't had an alert triggered yet.
        """
        now = time.time()
        
        # Clear active alert if its duration is over
        if self.active_alert and (now - self.last_alert_time > self.cooldown):
            self.active_alert = None

        new_alert = None

        for obj in tracked_objects:
            # Trigger alert when object is within trigger distance and has not been alerted
            if obj.distance <= self.trigger_distance and not obj.alert_triggered:
                # Set alert triggered
                obj.alert_triggered = True
                
                # Check cooldown to prevent duplicate noise
                if now - self.last_alert_time < 0.5:
                    continue
                
                # Determine alert properties
                alert_type = obj.class_name
                severity = obj.severity
                lat, lon = obj.gps
                speed = current_telemetry["speed_kmh"]
                
                self.last_alert_time = now
                self.active_alert = {
                    "id": obj.id,
                    "type": alert_type,
                    "severity": severity,
                    "distance": obj.distance,
                    "latitude": lat,
                    "longitude": lon,
                    "bbox": obj.bbox,
                    "timestamp": now
                }
                new_alert = self.active_alert
                
                # Record in metrics
                self.metrics.record_detection(alert_type, lat, lon, severity, obj.id)
                
                # Log detection to file & console
                LogManager.log_detection(
                    obstacle_type=alert_type,
                    lat=lat,
                    lon=lon,
                    severity=severity,
                    speed=speed,
                    obstacle_id=obj.id
                )
                
                # Trigger server-side audio notification in background thread
                threading.Thread(target=self._play_alert_sound, args=(alert_type, severity), daemon=True).start()

        return new_alert

    def _play_alert_sound(self, alert_type, severity):
        """
        Plays a non-blocking audio cue using winsound on Windows or a stdout bell on UNIX.
        """
        try:
            if winsound:
                # Pothole: Double high pitch beep
                if alert_type == "pothole":
                    # Beep at 1200Hz for 150ms
                    winsound.Beep(1200, 150)
                    time.sleep(0.08)
                    winsound.Beep(1200, 150)
                # Speed Bump: Low-high glide beep
                elif alert_type == "speed_bump":
                    winsound.Beep(600, 200)
                    winsound.Beep(900, 150)
                # Speed Limit: Two short medium pitch beeps
                elif alert_type == "speed_limit_60":
                    winsound.Beep(800, 100)
                    time.sleep(0.05)
                    winsound.Beep(800, 100)
                # Hard Turn: High warning slide beep
                elif alert_type == "hard_turn_ahead":
                    winsound.Beep(1000, 150)
                    time.sleep(0.05)
                    winsound.Beep(1000, 150)
                    time.sleep(0.05)
                    winsound.Beep(1000, 150)
            else:
                # Fallback to system bell
                sys.stdout.write('\a')
                sys.stdout.flush()
        except Exception as e:
            self.logger.warning(f"Failed to play server audio cue: {e}")
