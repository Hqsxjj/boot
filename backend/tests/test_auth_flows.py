import unittest
import json
import tempfile
import os

from werkzeug.security import generate_password_hash
import pyotp

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import create_app
from persistence.store import DataStore


class TestAuthFlows(unittest.TestCase):
    def setUp(self):
        self.temp_yaml = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yml')
        self.temp_yaml.close()

        self.temp_json = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_json.close()

        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()

        os.environ['DATA_PATH'] = self.temp_json.name
        os.environ['CONFIG_YAML_PATH'] = self.temp_yaml.name
        os.environ['DATABASE_URL'] = f'sqlite:///{self.temp_db.name}'

        self.app = create_app({
            'TESTING': True,
            'JWT_SECRET_KEY': 'test-secret',
            'SECRET_KEY': 'test-secret'
        })

        self.client = self.app.test_client()
        self.store = DataStore(self.temp_json.name, self.temp_yaml.name)

    def tearDown(self):
        if os.path.exists(self.temp_yaml.name):
            os.unlink(self.temp_yaml.name)
        if os.path.exists(self.temp_json.name):
            os.unlink(self.temp_json.name)
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def _login_and_get_token(self, password: str = 'testpass') -> str:
        self.store.update_admin_password(generate_password_hash(password))
        resp = self.client.post('/api/auth/login', json={'username': 'admin', 'password': password})
        self.assertEqual(resp.status_code, 200)
        payload = json.loads(resp.data)
        return payload['data']['token']

    def test_status_unauthenticated_defaults(self):
        resp = self.client.get('/api/auth/status')
        self.assertEqual(resp.status_code, 200)
        payload = json.loads(resp.data)

        self.assertTrue(payload['success'])
        self.assertIn('data', payload)
        data = payload['data']

        self.assertFalse(data['isAuthenticated'])
        self.assertFalse(data['isLocked'])
        self.assertEqual(data['failedAttempts'], 0)
        self.assertIn('is2FAVerified', data)

    def test_password_change_validates_current_password(self):
        token = self._login_and_get_token('oldpass')

        resp = self.client.put(
            '/api/auth/password',
            json={'currentPassword': 'wrong', 'newPassword': 'newpass'},
            headers={'Authorization': f'Bearer {token}'}
        )
        self.assertEqual(resp.status_code, 401)

        resp = self.client.put(
            '/api/auth/password',
            json={'currentPassword': 'oldpass', 'newPassword': 'newpass'},
            headers={'Authorization': f'Bearer {token}'}
        )
        self.assertEqual(resp.status_code, 200)
        payload = json.loads(resp.data)
        self.assertTrue(payload['success'])
        self.assertIn('data', payload)
        self.assertIn('isAuthenticated', payload['data'])

        # Old password should fail, new password should work
        resp = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'oldpass'})
        self.assertEqual(resp.status_code, 401)

        resp = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'newpass'})
        self.assertEqual(resp.status_code, 200)

    def test_logout_revokes_token_and_clears_2fa_verifier(self):
        secret = pyotp.random_base32()
        self.store.update_two_factor_secret(secret)

        token = self._login_and_get_token('testpass')

        # Not verified initially
        resp = self.client.get('/api/auth/status', headers={'Authorization': f'Bearer {token}'})
        payload = json.loads(resp.data)
        self.assertTrue(payload['success'])
        self.assertTrue(payload['data']['isAuthenticated'])
        self.assertFalse(payload['data']['is2FAVerified'])
        self.assertEqual(payload['data']['twoFactorSecret'], secret)

        # Verify OTP
        totp = pyotp.TOTP(secret)
        code = totp.now()
        resp = self.client.post(
            '/api/auth/verify-otp',
            json={'code': code},
            headers={'Authorization': f'Bearer {token}'}
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get('/api/auth/status', headers={'Authorization': f'Bearer {token}'})
        payload = json.loads(resp.data)
        self.assertTrue(payload['data']['is2FAVerified'])

        # Logout should revoke token and clear 2FA verifier
        resp = self.client.post('/api/auth/logout', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(resp.status_code, 200)

        # Revoked token should be rejected by protected endpoints
        resp = self.client.get('/api/config', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(resp.status_code, 401)

        # Status treats revoked token as unauthenticated
        resp = self.client.get('/api/auth/status', headers={'Authorization': f'Bearer {token}'})
        payload = json.loads(resp.data)
        self.assertTrue(payload['success'])
        self.assertFalse(payload['data']['isAuthenticated'])

    def test_lockout_after_failed_attempts(self):
        self.store.update_admin_password(generate_password_hash('correctpass'))

        for _ in range(5):
            resp = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrongpass'})
            self.assertEqual(resp.status_code, 401)

        resp = self.client.get('/api/auth/status')
        payload = json.loads(resp.data)
        self.assertTrue(payload['success'])
        self.assertTrue(payload['data']['isLocked'])
        self.assertEqual(payload['data']['failedAttempts'], 5)

        # Even correct credentials should not work once locked
        resp = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'correctpass'})
        self.assertEqual(resp.status_code, 423)

    def test_user_summary_alias(self):
        resp = self.client.get('/api/user/summary')
        self.assertEqual(resp.status_code, 200)
        payload = json.loads(resp.data)
        self.assertIn('data', payload)
        self.assertIn('isAuthenticated', payload['data'])


if __name__ == '__main__':
    unittest.main()
