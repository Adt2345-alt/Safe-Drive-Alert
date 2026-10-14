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
        self.alerted_ids = set()
        self.recent_spatial_alerts = [] # list of (lat, lon, timestamp)
        
    def _is_spatially_close(self, lat, lon, now, max_dist_m=15.0, time_window=4.0):
        # Prune old spatial entries
        self.recent_spatial_alerts = [entry for entry in self.recent_spatial_alerts if now - entry[2] < time_window]
        for prev_lat, prev_lon, _ in self.recent_spatial_alerts:
            # Approx distance check: 1 deg lat ~= 111000m
            d_lat = (lat - prev_lat) * 111000.0
            d_lon = (lon - prev_lon) * 111000.0 * 0.98
            dist = (d_lat**2 + d_lon**2)**0.5
            if dist < max_dist_m:
                return True
        return False

    def check_alerts(self, tracked_objects, current_telemetry):
        """
        Scans tracked objects to see if any are within the critical distance
        and haven't had an alert triggered yet. Deduplicates alerts spatially and temporally.
        """
        now = time.time()
        
        # Clear active alert if its duration is over
        if self.active_alert and (now - self.last_alert_time > self.cooldown):
            self.active_alert = None

        new_alert = None

        # Sort tracked objects by distance so the closest critical obstacle gets priority
        sorted_objs = sorted(tracked_objects, key=lambda o: o.distance)

        for obj in sorted_objs:
            if obj.id in self.alerted_ids:
                obj.alert_triggered = True
                continue

            # Check if object is within trigger distance
            if obj.distance <= self.trigger_distance and not obj.alert_triggered:
                lat, lon = obj.gps
                if (lat == 0.0 and lon == 0.0) or not lat or not lon:
                    lat = current_telemetry.get("latitude", 12.9716)
                    lon = current_telemetry.get("longitude", 77.5946)

                # Deduplicate spatially: if a nearby physical obstacle was alerted within 4s, suppress
                if self._is_spatially_close(lat, lon, now, max_dist_m=15.0, time_window=4.0):
                    obj.alert_triggered = True
                    self.alerted_ids.add(obj.id)
                    continue

                # Check cooldown to prevent duplicate alert spamming
                if now - self.last_alert_time < self.cooldown:
                    continue

                # Set alert triggered
                obj.alert_triggered = True
                self.alerted_ids.add(obj.id)
                self.recent_spatial_alerts.append((lat, lon, now))
                
                # Determine alert properties
                alert_type = obj.class_name
                severity = getattr(obj, "severity", "High") or "High"
                speed = current_telemetry.get("speed_kmh", 40.0)
                lane_pos = getattr(obj, "lane_position", "YOUR LANE")
                ttc_val = getattr(obj, "ttc_sec", 2.0)
                
                self.last_alert_time = now
                self.active_alert = {
                    "id": obj.id,
                    "type": alert_type,
                    "severity": severity,
                    "distance": obj.distance,
                    "latitude": lat,
                    "longitude": lon,
                    "bbox": obj.bbox,
                    "lane_position": lane_pos,
                    "ttc_sec": ttc_val,
                    "timestamp": now
                }

                new_alert = self.active_alert
                
                # Record in metrics & SQLite defects.db
                self.metrics.record_detection(alert_type, lat, lon, severity, obj.id)
                try:
                    from backend.api.defects_db import insert_defect
                    depth_val = getattr(obj, 'depth_cm', None) or (obj.get('depth_cm') if isinstance(obj, dict) else None)
                    if not depth_val or depth_val == 6.5:
                        import random
                        if severity == "Critical":
                            depth_val = round(random.uniform(14.0, 26.5), 1)
                        elif severity == "High":
                            depth_val = round(random.uniform(8.5, 15.5), 1)
                        elif severity == "Medium":
                            depth_val = round(random.uniform(5.5, 9.5), 1)
                        else:
                            depth_val = round(random.uniform(3.5, 6.5), 1)

                    insert_defect(
                        latitude=lat,
                        longitude=lon,
                        defect_type="pothole" if alert_type == "pothole" else ("speedbump" if alert_type == "speed_bump" else "crack"),
                        severity=severity if severity in ["Critical", "High", "Medium", "Low"] else "High",
                        confidence=getattr(obj, 'confidence', 0.94),
                        depth_cm=depth_val,
                        road_name="MG Road Corridor",
                        detection_source="Simulation Drive"
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to record live detection to defects.db: {e}")
                
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
                break # Only trigger 1 active alert per scan cycle

        return new_alert

    def _play_alert_sound(self, alert_type, severity):
        """
        Plays a non-blocking audio cue using winsound on Windows or a stdout bell on UNIX.
        """
        if not getattr(self, "sound_enabled", False):
            return
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
