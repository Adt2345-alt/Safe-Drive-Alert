import time

class KalmanFilter1D:
    """
    1D Linear Kalman Filter for smoothing vertical (Z-axis) accelerometer data.
    Filters out high-frequency road vibration noise while retaining true impact spikes.
    
    State Equation:
      x_k = x_{k-1} + w_k,  w_k ~ N(0, Q)
      z_k = x_k + v_k,      v_k ~ N(0, R)
    """
    def __init__(self, process_noise=0.01, measurement_noise=0.1, initial_value=1.0, initial_error=1.0):
        """
        :param process_noise: Q (variance of process noise)
        :param measurement_noise: R (variance of measurement noise)
        :param initial_value: Initial state estimate x_0 (1.0g baseline gravity)
        :param initial_error: Initial estimation error variance P_0
        """
        self.Q = process_noise
        self.R = measurement_noise
        self.x = initial_value
        self.P = initial_error

    def filter(self, measurement):
        """
        Predict and Update steps for a new 1D scalar measurement.
        :param measurement: Raw Z-axis acceleration in g units.
        :return: Filtered Z-axis state estimate (float).
        """
        # 1. Predict step
        # State prediction: x_k|k-1 = x_k-1
        x_pred = self.x
        # Error covariance prediction: P_k|k-1 = P_k-1 + Q
        P_pred = self.P + self.Q

        # 2. Update step
        # Kalman Gain: K_k = P_pred / (P_pred + R)
        K = P_pred / (P_pred + self.R)

        # State update: x_k = x_pred + K * (z_k - x_pred)
        self.x = x_pred + K * (measurement - x_pred)

        # Error covariance update: P_k = (1 - K) * P_pred
        self.P = (1.0 - K) * P_pred

        return self.x

    def reset(self, initial_value=1.0, initial_error=1.0):
        """Resets state variables."""
        self.x = initial_value
        self.P = initial_error
