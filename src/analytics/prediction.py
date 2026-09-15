import os
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

class PotholeGrowthPredictor:
    """
    30-Day Pothole Degradation & Growth Forecasting Model.
    Predicts the daily degradation trajectory of road potholes over 30 days
    based on initial severity, age (days), precipitation, freeze-thaw cycles, and traffic volume.
    Outputs: 'Will become critical in X days' and model evaluation metrics (MAE, RMSE, R^2).
    """
    def __init__(self, model_path=None):
        if model_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            model_path = os.path.join(base_dir, 'data', 'models', 'prophet_model.pkl')
            
        self.model_path = model_path
        self.model = None
        self._load_or_train_model()

    def _load_or_train_model(self):
        """Loads serialized model artifact or trains model on synthetic time series data."""
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                return
            except Exception:
                pass
        
        # Train & save model
        self.fit_synthetic_model()

    def fit_synthetic_model(self):
        """Trains degradation model on synthetic multi-feature time series dataset."""
        np.random.seed(42)
        n_samples = 1000

        # Features: [initial_severity (0.1-0.9), age_days (1-90), rain_mm (0-50), freeze_thaw (0-5), traffic_k_vpd (1-50)]
        init_sev = np.random.uniform(0.1, 0.7, n_samples)
        age = np.random.uniform(1, 60, n_samples)
        rain = np.random.uniform(0, 45, n_samples)
        freeze = np.random.randint(0, 4, n_samples)
        traffic = np.random.uniform(5, 45, n_samples)

        X = np.column_stack([init_sev, age, rain, freeze, traffic])
        
        # Degradation rate formula in 30 days
        y = init_sev + (age * 0.005) + (rain * 0.008) + (freeze * 0.08) + (traffic * 0.004) + np.random.normal(0, 0.03, n_samples)
        y = np.clip(y, 0.1, 1.0)

        self.model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.08, max_depth=4, random_state=42)
        self.model.fit(X, y)

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        with open(self.model_path, 'wb') as f:
            pickle.dump(self.model, f)

    def evaluate_performance(self):
        """Calculates and returns model evaluation metrics (MAE, RMSE, R^2)."""
        np.random.seed(99)
        n_test = 200
        init_sev = np.random.uniform(0.1, 0.7, n_test)
        age = np.random.uniform(1, 60, n_test)
        rain = np.random.uniform(0, 45, n_test)
        freeze = np.random.randint(0, 4, n_test)
        traffic = np.random.uniform(5, 45, n_test)

        X_test = np.column_stack([init_sev, age, rain, freeze, traffic])
        y_true = init_sev + (age * 0.005) + (rain * 0.008) + (freeze * 0.08) + (traffic * 0.004) + np.random.normal(0, 0.03, n_test)
        y_true = np.clip(y_true, 0.1, 1.0)

        y_pred = self.model.predict(X_test)

        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        r2 = r2_score(y_true, y_pred)

        return {
            "MAE": round(float(mae), 4),
            "RMSE": round(float(rmse), 4),
            "R2_Score": round(float(r2), 4)
        }

    def predict_growth_30_days(self, initial_severity=0.40, age_days=10, rain_mm=25.0, freeze_cycles=2, traffic_k_vpd=20.0):
        """
        Forecasts daily pothole degradation over the next 30 days.
        
        :return: dict with {daily_forecast: list, days_until_critical: int, status_message: str, final_severity: float}
        """
        daily_forecast = []
        days_until_critical = None

        curr_sev = initial_severity

        for day in range(1, 31):
            features = np.array([[curr_sev, age_days + day, rain_mm, freeze_cycles, traffic_k_vpd]])
            sev_next = float(self.model.predict(features)[0])
            # Ensure monotonicity
            curr_sev = max(curr_sev, min(1.0, curr_sev + (sev_next - curr_sev) * 0.25 + 0.015))
            daily_forecast.append({
                "day": day,
                "severity_index": round(curr_sev, 3),
                "is_critical": curr_sev >= 0.80
            })

            if curr_sev >= 0.80 and days_until_critical is None:
                days_until_critical = day

        if days_until_critical is not None:
            status_message = f"Will become critical in {days_until_critical} days"
        else:
            status_message = "Stable trajectory (Remaining safe > 30 days)"

        return {
            "initial_severity": round(initial_severity, 2),
            "final_30d_severity": round(curr_sev, 2),
            "days_until_critical": days_until_critical,
            "status_message": status_message,
            "daily_forecast": daily_forecast
        }
