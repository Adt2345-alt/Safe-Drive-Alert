import time
import random
import numpy as np
from collections import deque
from src.sensors.kalman_filter import KalmanFilter1D

class IMUReader:
    """
    MPU6050 6-DOF IMU Reader & Signal Processor.
    Samples accelerometer & gyroscope data at 100Hz.
    Smooths data using a 1D Kalman Filter and maintains a 500-sample circular buffer.
    Detects vertical (Z-axis) acceleration spikes exceeding 2.5g (pothole physical impact signature).
    """
    SPIKE_THRESHOLD = 2.5  # g-force threshold for pothole impact
    BUFFER_CAPACITY = 500  # 5 seconds at 100Hz
    SAMPLE_RATE_HZ = 100

    def __init__(self, spike_threshold=2.5, buffer_capacity=500):
        self.spike_threshold = spike_threshold
        self.buffer_capacity = buffer_capacity
        self.kalman = KalmanFilter1D(process_noise=0.02, measurement_noise=0.15, initial_value=1.0)
        
        # Buffer stores dicts: {timestamp, ax, ay, az_raw, az_filtered, gx, gy, gz, is_spike}
        self.buffer = deque(maxlen=self.buffer_capacity)
        self.last_sample_time = time.time()

    def process_reading(self, ax, ay, az_raw, gx, gy, gz, timestamp=None):
        """
        Processes a raw 6-DOF IMU reading at 100Hz.
        Applies Kalman filtering to Z-axis acceleration and checks spike condition.
        """
        if timestamp is None:
            timestamp = time.time()

        # Apply 1D Kalman Filter to vertical Z acceleration
        az_filtered = self.kalman.filter(az_raw)

        # Check for spike (> 2.5g raw or filtered threshold)
        is_spike = az_raw >= self.spike_threshold or az_filtered >= (self.spike_threshold * 0.85)

        sample = {
            "timestamp": timestamp,
            "ax": round(ax, 3),
            "ay": round(ay, 3),
            "az_raw": round(az_raw, 3),
            "az_filtered": round(az_filtered, 3),
            "gx": round(gx, 2),
            "gy": round(gy, 2),
            "gz": round(gz, 2),
            "is_spike": is_spike
        }

        self.buffer.append(sample)
        self.last_sample_time = timestamp
        return sample

    def get_spike_events(self, time_window_sec=0.5, current_time=None):
        """
        Queries recent buffer for Z-axis spikes within the given time window.
        Returns aggregated spike metadata including peak g-force and estimated confidence.
        """
        if current_time is None:
            current_time = time.time()

        start_time = current_time - time_window_sec
        recent_samples = [s for s in self.buffer if s["timestamp"] >= start_time]

        spikes = [s for s in recent_samples if s["is_spike"]]
        if not spikes:
            return None

        # Find maximum impact spike sample
        peak_sample = max(spikes, key=lambda s: max(s["az_raw"], s["az_filtered"]))
        peak_g = max(peak_sample["az_raw"], peak_sample["az_filtered"])

        # Calculate IMU confidence: 2.5g = 0.60, 4.0g+ = 0.98
        imu_confidence = min(0.98, max(0.50, 0.50 + (peak_g - self.spike_threshold) * 0.30))

        return {
            "timestamp": peak_sample["timestamp"],
            "peak_g_raw": peak_sample["az_raw"],
            "peak_g_filtered": peak_sample["az_filtered"],
            "confidence": round(imu_confidence, 2),
            "spike_count": len(spikes)
        }

    def simulate_100hz_batch(self, road_simulator, dt_sec=0.033):
        """
        Simulates 100Hz IMU samples during a 30 FPS camera frame interval (~33ms).
        Generates 3 to 4 IMU samples per frame, adding Z-axis spikes if car hits an obstacle.
        """
        now = time.time()
        num_samples = int(self.SAMPLE_RATE_HZ * dt_sec)
        num_samples = max(1, num_samples)
        
        # Check if car is currently hitting a pothole or bump (within 2.0 meters)
        impact_g = 1.0  # Baseline gravity (1.0g)
        if road_simulator and hasattr(road_simulator, 'obstacles'):
            for obs in road_simulator.obstacles:
                dist_to_obs = abs((obs["distance"] - road_simulator.current_distance) % road_simulator.total_path_length_meters)
                if dist_to_obs < 1.8:
                    if obs["type"] == "pothole":
                        impact_g = random.uniform(2.6, 4.2)
                    elif obs["type"] == "speed_bump":
                        impact_g = random.uniform(1.8, 2.4)
                    break

        samples = []
        for i in range(num_samples):
            sample_time = now - (num_samples - 1 - i) * (1.0 / self.SAMPLE_RATE_HZ)
            
            # Baseline road vibration noise (mean=1.0g, std=0.15g)
            vibration = random.gauss(0.0, 0.12)
            
            if impact_g > 2.0 and i == num_samples // 2:
                az_raw = impact_g + vibration
            else:
                az_raw = 1.0 + vibration

            ax = random.gauss(0.0, 0.05)
            ay = random.gauss(0.0, 0.05)
            gx = random.gauss(0.0, 1.0)
            gy = random.gauss(0.0, 1.0)
            gz = random.gauss(0.0, 1.0)

            sample = self.process_reading(ax, ay, az_raw, gx, gy, gz, timestamp=sample_time)
            samples.append(sample)

        return samples
