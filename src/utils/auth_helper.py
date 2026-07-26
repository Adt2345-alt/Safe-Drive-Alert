from flask import request, jsonify, redirect, url_for, make_response
from functools import wraps
from src.utils.jwt_helper import decode_jwt

# Role mapping permission matrix
ROLE_PERMISSIONS = {
    "ADMIN": [
        "view_dashboard", "live_feed", "export_data", "manage_users",
        "delete_records", "system_settings", "generate_reports",
        "acknowledge_alerts", "submit_reports", "view_analytics"
    ],
    "OPERATOR": [
        "view_dashboard", "live_feed", "export_data", "generate_reports",
        "acknowledge_alerts", "submit_reports", "view_analytics"
    ],
    "VIEWER": [
        "view_dashboard", "live_feed", "view_analytics"
    ],
    "DRIVER": [
        "view_dashboard", "live_feed"
    ],
    "MUNICIPALITY": [
        "view_dashboard", "live_feed", "export_data", "generate_reports",
        "acknowledge_alerts", "submit_reports", "view_analytics"
    ]
}

def get_current_user():
    token = request.cookies.get("access_token")
    if not token and request.headers.get("Authorization"):
        auth_header = request.headers.get("Authorization")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    if not token:
        return None
    return decode_jwt(token)

def requires_auth(permission=None):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Authentication required"}), 401
                return redirect(url_for("login"))
            
            role = user.get("role")
            permissions = ROLE_PERMISSIONS.get(role, [])
            
            if permission and permission not in permissions:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Forbidden: insufficient permissions"}), 403
                return redirect(url_for("login")) # Redirect to login page on browser failure
            
            request.user = user
            return f(*args, **kwargs)
        return decorated
    return decorator
