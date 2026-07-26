import base64
import json
import hmac
import hashlib
import time

SECRET_KEY = b"safe_drive_alert_cyber_security_secret_2026"

def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip("=")

def base64url_decode(data: str) -> bytes:
    padding = '=' * (4 - len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode('utf-8'))

def encode_jwt(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = base64url_encode(json.dumps(header).encode('utf-8'))
    payload_part = base64url_encode(json.dumps(payload).encode('utf-8'))
    msg = f"{header_part}.{payload_part}"
    sig = hmac.new(SECRET_KEY, msg.encode('utf-8'), hashlib.sha256).digest()
    sig_part = base64url_encode(sig)
    return f"{msg}.{sig_part}"

def decode_jwt(token: str) -> dict:
    """
    Decodes and validates a JWT token. Returns payload dict if valid, or None if invalid.
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header_part, payload_part, sig_part = parts
        msg = f"{header_part}.{payload_part}"
        expected_sig = hmac.new(SECRET_KEY, msg.encode('utf-8'), hashlib.sha256).digest()
        actual_sig = base64url_decode(sig_part)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(base64url_decode(payload_part).decode('utf-8'))
        if "exp" in payload and payload["exp"] < time.time():
            return None # Expired
        return payload
    except Exception:
        return None
