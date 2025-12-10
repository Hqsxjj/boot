import unittest
import json
import tempfile
import os
import shutil
from types import SimpleNamespace
from unittest.mock import patch
from werkzeug.security import generate_password_hash
import pyotp

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import create_app
from persistence.store import DataStore
from services.job_runner import job_runner
from services.webdav import webdav_server


class TestFlaskApp(unittest.TestCase):
    """Test Flask application endpoints."""
    
    def setUp(self):
        """Set up test client and temporary data file."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        
        # Override data path BEFORE creating app
        os.environ['DATA_PATH'] = self.temp_file.name
        
        self.app = create_app({
            'TESTING': True,
            'JWT_SECRET_KEY': 'test-secret',
            'SECRET_KEY': 'test-secret'
        })
        
        self.client = self.app.test_client()
        self.store = DataStore(self.temp_file.name)
    
    def tearDown(self):
        """Clean up temporary file."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def _auth_headers(self):
        """Helper to obtain auth headers for integration endpoints."""
        token = getattr(self, "_auth_token", None)
        if token:
            return {"Authorization": f"Bearer {token}"}
        password = "secretpass"
        self.store.update_admin_password(generate_password_hash(password))
        response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': password},
            content_type='application/json'
        )
        data = json.loads(response.data)
        token = data['data']['token']
        self._auth_token = token
        return {"Authorization": f"Bearer {token}"}
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['status'], 'healthy')
    
    def test_root_endpoint(self):
        """Test root endpoint."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('service', data['data'])
    
    def test_login_first_time(self):
        """Test first-time login (password setup)."""
        response = self.client.post('/api/auth/login', 
            json={'username': 'admin', 'password': 'newpassword123'},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('token', data['data'])
        self.assertFalse(data['data']['requires2FA'])
    
    def test_login_with_wrong_credentials(self):
        """Test login with wrong credentials."""
        # First, set up password
        self.store.update_admin_password(generate_password_hash('correctpass'))
        
        response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'wrongpass'},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_login_with_correct_credentials(self):
        """Test login with correct credentials."""
        # Set up password
        self.store.update_admin_password(generate_password_hash('correctpass'))
        
        response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'correctpass'},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('token', data['data'])
    
    def test_get_config_without_auth(self):
        """Test getting config without authentication."""
        response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 401)
    
    def test_get_config_with_auth(self):
        """Test getting config with authentication."""
        # Login first
        self.store.update_admin_password(generate_password_hash('testpass'))
        login_response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'testpass'},
            content_type='application/json'
        )
        token = json.loads(login_response.data)['data']['token']
        
        # Get config
        response = self.client.get('/api/config',
            headers={'Authorization': f'Bearer {token}'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('telegram', data['data'])
        self.assertIn('cloud115', data['data'])
    
    def test_update_config_with_auth(self):
        """Test updating config with authentication."""
        # Login first
        self.store.update_admin_password(generate_password_hash('testpass'))
        login_response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'testpass'},
            content_type='application/json'
        )
        token = json.loads(login_response.data)['data']['token']
        
        # Update config
        new_config = self.store.get_config()
        new_config['telegram']['botToken'] = 'new-token-123'
        
        response = self.client.put('/api/config',
            json=new_config,
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['telegram']['botToken'], 'new-token-123')
    
    def test_verify_otp_without_2fa_setup(self):
        """Test OTP verification without 2FA setup."""
        # Login first
        self.store.update_admin_password(generate_password_hash('testpass'))
        login_response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'testpass'},
            content_type='application/json'
        )
        token = json.loads(login_response.data)['data']['token']
        
        # Try to verify OTP
        response = self.client.post('/api/auth/verify-otp',
            json={'code': '123456'},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_setup_2fa(self):
        """Test 2FA setup."""
        # Login first
        self.store.update_admin_password(generate_password_hash('testpass'))
        login_response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'testpass'},
            content_type='application/json'
        )
        token = json.loads(login_response.data)['data']['token']
        
        # Setup 2FA
        response = self.client.post('/api/auth/setup-2fa',
            headers={'Authorization': f'Bearer {token}'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('secret', data['data'])
        self.assertIn('qrCodeUri', data['data'])
    
    def test_verify_otp_with_valid_code(self):
        """Test OTP verification with valid code."""
        # Setup 2FA
        secret = pyotp.random_base32()
        self.store.update_two_factor_secret(secret)
        
        # Login
        self.store.update_admin_password(generate_password_hash('testpass'))
        login_response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'testpass'},
            content_type='application/json'
        )
        token = json.loads(login_response.data)['data']['token']
        
        # Generate valid OTP
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        
        # Verify OTP
        response = self.client.post('/api/auth/verify-otp',
            json={'code': valid_code},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertTrue(data['data']['verified'])
    
    def test_get_me_endpoint(self):
        """Test /api/me endpoint."""
        # Login first
        self.store.update_admin_password(generate_password_hash('testpass'))
        login_response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'testpass'},
            content_type='application/json'
        )
        token = json.loads(login_response.data)['data']['token']

        # Get user info
        response = self.client.get('/api/me',
            headers={'Authorization': f'Bearer {token}'}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['username'], 'admin')

    @patch('blueprints.p115.P115Bridge')
    def test_p115_cookie_login_endpoint(self, mock_bridge):
        """Ensure /api/115/login updates config via P115Bridge."""
        headers = self._auth_headers()
        instance = mock_bridge.return_value
        instance.get_user_profile.return_value = {'uid': 'u1'}
        instance.check_login.return_value = True
        payload = {
            'cookies': 'UID=demo;',
            'userAgent': 'Mozilla/5.0',
            'loginApp': 'web'
        }
        response = self.client.post('/api/115/login',
            json=payload,
            headers=headers,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        updated = self.store.get_config()
        self.assertEqual(updated['cloud115']['cookies'], 'UID=demo;')
        mock_bridge.assert_called_once()

    @patch('blueprints.p115._get_bridge')
    def test_p115_folder_listing(self, mock_get_bridge):
        """Ensure folders endpoint proxies to bridge."""
        headers = self._auth_headers()
        stub = SimpleNamespace(list_folders=lambda **kwargs: {'cid': kwargs['cid'], 'items': [{'id': '1'}]})
        mock_get_bridge.return_value = stub
        response = self.client.get('/api/115/folders?cid=0&limit=5', headers=headers)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['data']['cid'], '0')
        self.assertEqual(len(data['data']['items']), 1)

    def test_strm_job_queue(self):
        """Queue a STRM job and ensure it completes."""
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir)
        config = self.store.get_config()
        config['strm']['outputDir'] = tmpdir
        self.store.update_config(config)
        headers = self._auth_headers()
        response = self.client.post('/api/strm/run', json={'module': '115'}, headers=headers, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        job_id = json.loads(response.data)['data']['jobId']
        job_runner.wait_for(job_id, timeout=5)
        job_response = self.client.get(f'/api/strm/jobs/{job_id}', headers=headers)
        job_data = json.loads(job_response.data)
        self.assertEqual(job_data['data']['status'], 'finished')

    def test_webdav_lifecycle(self):
        """Start and stop the internal WebDAV server."""
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir)
        self.addCleanup(webdav_server.stop)
        config = self.store.get_config()
        config['strm']['outputDir'] = tmpdir
        config['strm']['webdav']['port'] = '0'
        config['strm']['webdav']['username'] = 'user'
        config['strm']['webdav']['password'] = 'pass'
        self.store.update_config(config)
        headers = self._auth_headers()
        start_resp = self.client.post('/api/strm/webdav/start', headers=headers)
        self.assertEqual(start_resp.status_code, 200)
        start_data = json.loads(start_resp.data)
        self.assertTrue(start_data['data']['running'])
        stop_resp = self.client.post('/api/strm/webdav/stop', headers=headers)
        stop_data = json.loads(stop_resp.data)
        self.assertFalse(stop_data['data']['running'])

    @patch('blueprints.emby.emby_service.test_connection')
    def test_emby_connection_test_route(self, mock_test_connection):
        """Emby connection endpoint proxies to helper."""
        mock_test_connection.return_value = {'version': '1.0.0'}
        headers = self._auth_headers()
        response = self.client.post('/api/emby/test',
            json={'serverUrl': 'http://emby.local', 'apiKey': 'abc'},
            headers=headers,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['data']['version'], '1.0.0')

    @patch('blueprints.emby.emby_service.fetch_missing_episodes')
    def test_emby_missing_endpoint(self, mock_fetch_missing):
        """Missing episodes endpoint returns remote data."""
        mock_fetch_missing.return_value = [{'series': 'Demo', 'episodeName': 'Pilot'}]
        config = self.store.get_config()
        config['emby']['serverUrl'] = 'http://emby.local'
        config['emby']['apiKey'] = 'abc'
        self.store.update_config(config)
        headers = self._auth_headers()
        response = self.client.get('/api/emby/missing', headers=headers)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['data']['count'], 1)

    def test_webhook_ingest_and_recent(self):
        """Webhook endpoint should store events for later inspection."""
        from blueprints import webhook as webhook_module
        webhook_module._RECENT_EVENTS.clear()
        payload = {'event': 'PlaybackStart'}
        ingest_resp = self.client.post('/api/webhook/115bot', json=payload, content_type='application/json')
        self.assertEqual(ingest_resp.status_code, 200)
        headers = self._auth_headers()
        recent_resp = self.client.get('/api/webhook/recent', headers=headers)
        data = json.loads(recent_resp.data)
        self.assertGreaterEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['payload']['event'], 'PlaybackStart')


class TestDataStore(unittest.TestCase):

    
    def setUp(self):
        """Set up temporary data file."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.store = DataStore(self.temp_file.name)
    
    def tearDown(self):
        """Clean up temporary file."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_default_config_structure(self):
        """Test that default config has correct structure."""
        config = self.store.get_config()
        
        self.assertIn('telegram', config)
        self.assertIn('cloud115', config)
        self.assertIn('cloud123', config)
        self.assertIn('openList', config)
        self.assertIn('proxy', config)
        self.assertIn('tmdb', config)
        self.assertIn('emby', config)
        self.assertIn('strm', config)
        self.assertIn('organize', config)
    
    def test_update_and_retrieve_config(self):
        """Test config serialization and deserialization."""
        config = self.store.get_config()
        config['telegram']['botToken'] = 'test-token-123'
        config['telegram']['adminUserId'] = '12345'
        
        self.store.update_config(config)
        
        retrieved = self.store.get_config()
        self.assertEqual(retrieved['telegram']['botToken'], 'test-token-123')
        self.assertEqual(retrieved['telegram']['adminUserId'], '12345')
    
    def test_admin_password_update(self):
        """Test admin password storage."""
        password_hash = generate_password_hash('testpassword')
        self.store.update_admin_password(password_hash)
        
        admin = self.store.get_admin_credentials()
        self.assertEqual(admin['password_hash'], password_hash)
    
    def test_two_factor_secret_storage(self):
        """Test 2FA secret storage."""
        secret = pyotp.random_base32()
        self.store.update_two_factor_secret(secret)
        
        retrieved = self.store.get_two_factor_secret()
        self.assertEqual(retrieved, secret)
        self.assertTrue(self.store.is_two_factor_enabled())
    
    def test_config_with_2fa_secret(self):
        """Test that 2FA secret is included in config when enabled."""
        secret = pyotp.random_base32()
        self.store.update_two_factor_secret(secret)
        
        config = self.store.get_config()
        self.assertIn('twoFactorSecret', config)
        self.assertEqual(config['twoFactorSecret'], secret)


if __name__ == '__main__':
    unittest.main()
