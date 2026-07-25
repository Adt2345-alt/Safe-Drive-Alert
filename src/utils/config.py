import os

class Config:
    # App root directories
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    LOGS_DIR = os.path.join(DATA_DIR, 'logs')
    MODELS_DIR = os.path.join(DATA_DIR, 'models')

    # Ensure directories exist
    for directory in [DATA_DIR, LOGS_DIR, MODELS_DIR]:
        os.makedirs(directory, exist_ok=True)

    # Server Configuration
    HOST = "0.0.0.0"
    PORT = 5000
    DEBUG = False

    # Video Generator Settings
    FRAME_WIDTH = 640
    FRAME_HEIGHT = 480
    FPS = 25

    # AI Detection & Tracking Thresholds
    DETECTION_CONF_THRESHOLD = 0.5
    TRACKING_MAX_DISAPPEARED = 10  # frames
    TRACKING_MIN_DISTANCE_PIXELS = 50 # centroid distance to match

    # Alert System Settings
    ALERT_TRIGGER_DISTANCE = 15.0  # meters (critical distance to trigger alert)
    COOLDOWN_PERIOD_SECONDS = 3.0  # prevent spamming alerts for the same physical object

    # GPS Parameters
    GPS_SAMPLE_RATE_HZ = 5
    GPS_JITTER_STD = 0.00001  # Simulated GPS variance

    # Road Simulation Scenarios
    SCENARIOS = {
        "city_commute": {
            "name": "City Commute",
            "base_speed": 40.0,  # km/h
            "max_speed": 60.0,
            "obstacle_frequency": 0.08, # probability of obstacle generation per unit distance
            "pothole_ratio": 0.4,       # 40% potholes, 60% speed bumps
            "sign_frequency": 0.05,     # signs per 100 meters
            "description": "Navigate a standard city route with moderate speeds, traffic lights, intersections, speed bumps, and occasional potholes."
        },
        "highway_journey": {
            "name": "Highway Journey",
            "base_speed": 90.0,
            "max_speed": 110.0,
            "obstacle_frequency": 0.01,
            "pothole_ratio": 0.9,       # Mostly potholes
            "sign_frequency": 0.03,
            "description": "High-speed cruising. Obstacles are rare but dangerous. Zero speed bumps, only occasional unexpected potholes."
        },
        "pothole_alley": {
            "name": "Pothole Alley",
            "base_speed": 25.0,
            "max_speed": 35.0,
            "obstacle_frequency": 0.25, # High density of road damage
            "pothole_ratio": 0.85,      # Mostly potholes
            "sign_frequency": 0.01,
            "description": "A severely degraded rural road with a very high frequency of deep potholes. Drive slow to avoid vehicle damage."
        }
    }

    DEFAULT_SCENARIO = "city_commute"
