import unittest
import sys
import os
import time

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.db import init_db, get_user_by_username, verify_password, hash_password, get_all_users
from src.utils.jwt_helper import encode_jwt, decode_jwt
from src.api.web_dashboard import app

class TestAuthAndRBAC(unittest.TestCase):
    def setUp(self):
        # Setup testing database
        init_db()
        self.app = app.test_client()
        self.app.testing = True

    def test_password_hashing(self):
        pw = "supersecret123"
        hashed = hash_password(pw)
        self.assertNotEqual(pw, hashed)
        self.assertTrue(verify_password(pw, hashed))
        self.assertFalse(verify_password("wrongpassword", hashed))

    def test_default_users_seeded(self):
        admin = get_user_by_username("admin")
        self.assertIsNotNone(admin)
        self.assertEqual(admin["role"], "ADMIN")
        self.assertTrue(verify_password("admin123", admin["password_hash"]))

        driver = get_user_by_username("driver")
        self.assertIsNotNone(driver)
        self.assertEqual(driver["role"], "DRIVER")
        self.assertTrue(verify_password("driver123", driver["password_hash"]))

    def test_jwt_tokens(self):
        payload = {"username": "test_user", "role": "OPERATOR", "exp": time.time() + 10}
        token = encode_jwt(payload)
        
        # Valid decode
        decoded = decode_jwt(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["username"], "test_user")
        self.assertEqual(decoded["role"], "OPERATOR")
        
        # Tampered signature decode should fail
        tampered_token = token[:-4] + "AAAA"
        self.assertIsNone(decode_jwt(tampered_token))
        
        # Expired token decode should fail
        expired_payload = {"username": "old_user", "role": "VIEWER", "exp": time.time() - 10}
        expired_token = encode_jwt(expired_payload)
        self.assertIsNone(decode_jwt(expired_token))

    def test_route_redirection_unauthenticated(self):
        # Accessing dashboard without authentication cookie should redirect to login
        response = self.app.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_api_rejection_unauthenticated(self):
        # Accessing API endpoints without auth should return 401 Unauthorized
        response = self.app.get('/api/telemetry')
        self.assertEqual(response.status_code, 401)

    def test_login_flow(self):
        # Login with correct credentials
        response = self.app.post('/login', json={
            "username": "admin",
            "password": "admin123"
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["role"], "ADMIN")
        self.assertIn("token", data)

        # Login with bad credentials
        response = self.app.post('/login', json={
            "username": "admin",
            "password": "badpassword"
        })
        self.assertEqual(response.status_code, 401)

    def test_rbac_endpoint_access(self):
        # Create an operator token
        op_token = encode_jwt({
            "username": "operator",
            "role": "OPERATOR",
            "exp": time.time() + 60
        })
        
        # Admin token
        admin_token = encode_jwt({
            "username": "admin",
            "role": "ADMIN",
            "exp": time.time() + 60
        })

        # Set cookie and call admin endpoint as Operator (should return 403 Forbidden)
        self.app.set_cookie('access_token', op_token)
        response = self.app.get('/api/admin/users')
        self.assertEqual(response.status_code, 403)

        # Call admin endpoint as Admin (should return 200 OK)
        self.app.set_cookie('access_token', admin_token)
        response = self.app.get('/api/admin/users')
        self.assertEqual(response.status_code, 200)

        # Try to pause simulation as Viewer (requires system_settings permission)
        viewer_token = encode_jwt({
            "username": "viewer",
            "role": "VIEWER",
            "exp": time.time() + 60
        })
        self.app.set_cookie('access_token', viewer_token)
        response = self.app.post('/api/control', json={"action": "toggle_pause"})
        self.assertEqual(response.status_code, 403)

if __name__ == '__main__':
    unittest.main()
