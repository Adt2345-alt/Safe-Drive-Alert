import logging
import os
import sys
from datetime import datetime
from src.utils.config import Config

class LogManager:
    _system_logger = None
    _detection_logger = None

    @classmethod
    def get_system_logger(cls):
        if cls._system_logger is not None:
            return cls._system_logger

        # Setup main system logger
        logger = logging.getLogger("SafeDriveAlertSystem")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        # Formatters
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File Handler
        log_file = os.path.join(Config.LOGS_DIR, "system.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        cls._system_logger = logger
        return logger

    @classmethod
    def get_detection_logger(cls):
        if cls._detection_logger is not None:
            return cls._detection_logger

        # Setup detection logger for anomalies log
        logger = logging.getLogger("SafeDriveAlertDetections")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        # Anomaly logger format
        formatter = logging.Formatter('%(message)s')

        # Log file
        log_file = os.path.join(Config.LOGS_DIR, "detections.csv")
        
        # Write headers if file doesn't exist
        if not os.path.exists(log_file):
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("timestamp,type,latitude,longitude,severity,speed_kmh,obstacle_id\n")

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        cls._detection_logger = logger
        return logger

    @classmethod
    def log_detection(cls, obstacle_type, lat, lon, severity, speed, obstacle_id):
        det_logger = cls.get_detection_logger()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"{timestamp},{obstacle_type},{lat:.6f},{lon:.6f},{severity},{speed:.1f},{obstacle_id}"
        det_logger.info(log_entry)

        # Also log to system logger for traceability
        sys_logger = cls.get_system_logger()
        sys_logger.info(f"Anomaly Registered: {obstacle_type.upper()} [ID: {obstacle_id}] at ({lat:.6f}, {lon:.6f}) Severity: {severity} Speed: {speed:.1f} km/h")
