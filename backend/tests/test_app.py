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


class TestFlaskApp(unittest.TestCase):
    """Test Flask application endpoints."""
    
    def setUp(self):
        """Set up test client and temporary data file."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        
        # Override data path BEFORE creating app
        os.environ['DATA_PATH'] = self.temp_file.name
        os.environ['DATABASE_URL'] = f'sqlite:///{self.temp_db.name}'
        
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
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
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
        # Token should NOT be masked - full round-trip with YAML store
        returned_token = data['data']['telegram']['botToken']
        self.assertEqual(returned_token, 'new-token-123')
    
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


class TestDataStore(unittest.TestCase):
    """Test DataStore persistence layer."""
    
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
