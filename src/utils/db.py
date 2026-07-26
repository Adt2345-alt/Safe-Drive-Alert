import sqlite3
import os
import hashlib
import base64
import hmac
import datetime
from src.utils.config import Config

DB_PATH = os.path.join(Config.DATA_DIR, "safe_drive.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Cryptographic password hashing
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    salt_b64 = base64.b64encode(salt).decode('utf-8')
    hash_b64 = base64.b64encode(pw_hash).decode('utf-8')
    return f"{salt_b64}:{hash_b64}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        parts = stored_hash.split(':')
        if len(parts) != 2:
            return False
        salt_b64, hash_b64 = parts
        salt = base64.b64decode(salt_b64)
        pw_hash = base64.b64decode(hash_b64)
        test_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return hmac.compare_digest(pw_hash, test_hash)
    except Exception:
        return False

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        region TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create Audit Logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        role TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create Work Orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS work_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        obstacle_id INTEGER,
        type TEXT NOT NULL,
        description TEXT,
        assigned_driver TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'assigned',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create Defects History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS defects_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        severity TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'unresolved',
        reported_by TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Seed default users if users table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ("admin", "admin123", "ADMIN", "Global"),
            ("operator", "operator123", "OPERATOR", "North District"),
            ("viewer", "viewer123", "VIEWER", "Public"),
            ("driver", "driver123", "DRIVER", "Route 66"),
            ("municipality", "municipality123", "MUNICIPALITY", "City Hall")
        ]
        for username, password, role, region in default_users:
            pw_hash = hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, region) VALUES (?, ?, ?, ?)",
                (username, pw_hash, role, region)
            )
        conn.commit()
        
    conn.close()

# User Management Functions
def get_user_by_username(username: str):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return user

def create_user(username: str, password_hash: str, role: str, region: str = None):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, region) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, region)
        )
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def delete_user(username: str):
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_db_connection()
    users = conn.execute("SELECT id, username, role, region, created_at FROM users").fetchall()
    conn.close()
    return [dict(u) for u in users]

# Audit Logging Functions
def log_audit(username: str, role: str, action: str, details: str):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO audit_logs (username, role, action, details) VALUES (?, ?, ?, ?)",
        (username, role, action, details)
    )
    conn.commit()
    conn.close()

def get_audit_logs():
    conn = get_db_connection()
    logs = conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(l) for l in logs]

# Work Orders Functions
def create_work_order(obstacle_id: int, obs_type: str, description: str, assigned_driver: str):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO work_orders (obstacle_id, type, description, assigned_driver) VALUES (?, ?, ?, ?)",
        (obstacle_id, obs_type, description, assigned_driver)
    )
    conn.commit()
    conn.close()

def get_work_orders():
    conn = get_db_connection()
    orders = conn.execute("SELECT * FROM work_orders ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(o) for o in orders]

def update_work_order_status(order_id: int, status: str):
    conn = get_db_connection()
    conn.execute("UPDATE work_orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()

# Defects Functions
def report_defect(defect_type: str, latitude: float, longitude: float, severity: str, status: str = "unresolved", reported_by: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO defects_history (type, latitude, longitude, severity, status, reported_by) VALUES (?, ?, ?, ?, ?, ?)",
        (defect_type, latitude, longitude, severity, status, reported_by)
    )
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id

def get_defects():
    conn = get_db_connection()
    defects = conn.execute("SELECT * FROM defects_history ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(d) for d in defects]

# Initialize on import to make sure tables are setup
init_db()
