import unittest
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from werkzeug.security import generate_password_hash

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import create_app
from persistence.store import DataStore
from models.database import init_db, get_session_factory


class TestCloud115Blueprint(unittest.TestCase):
    """Test 115 cloud blueprint endpoints."""
    
    def setUp(self):
        """Set up test client and temporary data file."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        
        # Override paths BEFORE creating app
        os.environ['DATA_PATH'] = self.temp_file.name
        os.environ['DATABASE_URL'] = f'sqlite:///{self.temp_db.name}'
        os.environ['SECRETS_ENCRYPTION_KEY'] = 'test-encryption-key-32-chars-long!!'
        
        self.app = create_app({
            'TESTING': True,
            'JWT_SECRET_KEY': 'test-secret',
            'SECRET_KEY': 'test-secret'
        })
        
        self.client = self.app.test_client()
        self.store = DataStore(self.temp_file.name)
        
        # Set up admin for authentication
        self.store.update_admin_password(generate_password_hash('testpass'))
        
        # Get auth token
        login_response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'testpass'},
            content_type='application/json'
        )
        self.token = json.loads(login_response.data)['data']['token']
        self.auth_header = {'Authorization': f'Bearer {self.token}'}
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    @patch('p115_bridge.P115Service.start_qr_login')
    def test_start_qr_login_success(self, mock_start_qr):
        """Test starting a QR code login."""
        mock_start_qr.return_value = {
            'sessionId': 'test-session-id',
            'qrcode': 'test-qr-code-data',
            'login_method': 'cookie',
            'login_app': 'web'
        }
        
        response = self.client.post('/api/115/login/qrcode',
            json={
                'loginApp': 'web',
                'loginMethod': 'cookie'
            },
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('sessionId', data['data'])
        self.assertIn('qrcode', data['data'])
        self.assertEqual(data['data']['loginMethod'], 'cookie')
        self.assertEqual(data['data']['loginApp'], 'web')
    
    def test_start_qr_login_without_auth(self):
        """Test starting QR login without authentication."""
        response = self.client.post('/api/115/login/qrcode',
            json={
                'loginApp': 'web',
                'loginMethod': 'cookie'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)
    
    def test_start_qr_login_invalid_method(self):
        """Test starting QR login with invalid login method."""
        response = self.client.post('/api/115/login/qrcode',
            json={
                'loginApp': 'web',
                'loginMethod': 'invalid'
            },
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    @patch('p115_bridge.P115Service.poll_login_status')
    def test_poll_login_status_nonexistent_session(self, mock_poll):
        """Test polling status for non-existent session."""
        mock_poll.return_value = {
            'success': False,
            'error': 'Session not found'
        }
        
        response = self.client.get('/api/115/login/status/nonexistent-session',
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_ingest_cookies_without_auth(self):
        """Test ingesting cookies without authentication."""
        response = self.client.post('/api/115/login/cookie',
            json={
                'cookies': {
                    'UID': 'test_uid'
                }
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)
    
    def test_ingest_cookies_missing_data(self):
        """Test ingesting cookies with missing data."""
        response = self.client.post('/api/115/login/cookie',
            json={},
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    @patch('p115_bridge.P115Service.validate_cookies')
    def test_ingest_cookies_invalid_format(self, mock_validate):
        """Test ingesting cookies with invalid format."""
        response = self.client.post('/api/115/login/cookie',
            json={
                'cookies': 'not-a-dict'
            },
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_get_session_health_no_session(self):
        """Test getting session health with no session."""
        response = self.client.get('/api/115/session',
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertFalse(data['data']['hasValidSession'])
    
    def test_get_session_health_without_auth(self):
        """Test getting session health without authentication."""
        response = self.client.get('/api/115/session')
        
        self.assertEqual(response.status_code, 401)


class TestSecretStore(unittest.TestCase):
    """Test SecretStore for secret persistence."""
    
    def setUp(self):
        """Set up temporary database."""
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        
        os.environ['DATABASE_URL'] = f'sqlite:///{self.temp_db.name}'
        os.environ['SECRETS_ENCRYPTION_KEY'] = 'test-encryption-key-32-chars-long!!'
        
        # Initialize database
        from models.database import init_db, get_session_factory
        engine = init_db()
        session_factory = get_session_factory(engine)
        
        from services.secret_store import SecretStore
        self.secret_store = SecretStore(session_factory)
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_set_and_get_secret(self):
        """Test setting and retrieving a secret."""
        key = 'test_secret'
        value = 'super_secret_value'
        
        # Set secret
        success = self.secret_store.set_secret(key, value)
        self.assertTrue(success)
        
        # Get secret
        retrieved = self.secret_store.get_secret(key)
        self.assertEqual(retrieved, value)
    
    def test_secret_encryption(self):
        """Test that secrets are encrypted."""
        key = 'cloud115_cookies'
        value = '{"UID": "test123", "CID": "secret"}'
        
        # Set secret
        self.secret_store.set_secret(key, value)
        
        # Get from database directly to verify encryption
        from models.secret import Secret
        session = self.secret_store.session_factory()
        secret_obj = session.query(Secret).filter(Secret.key == key).first()
        session.close()
        
        # Verify that stored value is encrypted (not equal to original)
        self.assertIsNotNone(secret_obj)
        self.assertNotEqual(secret_obj.encrypted_value, value)
        
        # But decryption should work
        retrieved = self.secret_store.get_secret(key)
        self.assertEqual(retrieved, value)
    
    def test_secret_exists(self):
        """Test checking if secret exists."""
        key = 'test_key'
        value = 'test_value'
        
        # Before setting
        self.assertFalse(self.secret_store.secret_exists(key))
        
        # After setting
        self.secret_store.set_secret(key, value)
        self.assertTrue(self.secret_store.secret_exists(key))
    
    def test_delete_secret(self):
        """Test deleting a secret."""
        key = 'test_key'
        value = 'test_value'
        
        # Set and delete
        self.secret_store.set_secret(key, value)
        success = self.secret_store.delete_secret(key)
        self.assertTrue(success)
        
        # Verify deleted
        self.assertFalse(self.secret_store.secret_exists(key))
        self.assertIsNone(self.secret_store.get_secret(key))
    
    def test_update_secret(self):
        """Test updating an existing secret."""
        key = 'test_key'
        value1 = 'original_value'
        value2 = 'updated_value'
        
        # Set initial value
        self.secret_store.set_secret(key, value1)
        self.assertEqual(self.secret_store.get_secret(key), value1)
        
        # Update value
        self.secret_store.set_secret(key, value2)
        self.assertEqual(self.secret_store.get_secret(key), value2)


class TestConfigSecretMasking(unittest.TestCase):
    """Test config secret masking functionality."""
    
    def setUp(self):
        """Set up test client and temporary data file."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        
        # Override paths BEFORE creating app
        os.environ['DATA_PATH'] = self.temp_file.name
        os.environ['DATABASE_URL'] = f'sqlite:///{self.temp_db.name}'
        os.environ['SECRETS_ENCRYPTION_KEY'] = 'test-encryption-key-32-chars-long!!'
        
        self.app = create_app({
            'TESTING': True,
            'JWT_SECRET_KEY': 'test-secret',
            'SECRET_KEY': 'test-secret'
        })
        
        self.client = self.app.test_client()
        self.store = DataStore(self.temp_file.name)
        
        # Set up admin for authentication
        self.store.update_admin_password(generate_password_hash('testpass'))
        
        # Get auth token
        login_response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'testpass'},
            content_type='application/json'
        )
        self.token = json.loads(login_response.data)['data']['token']
        self.auth_header = {'Authorization': f'Bearer {self.token}'}
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_config_update_returns_unmasked_sensitive_fields(self):
        """Test that sensitive fields are returned without masking."""
        config = self.store.get_config()
        config['telegram']['botToken'] = 'my-secret-bot-token-12345'
        
        response = self.client.put('/api/config',
            json=config,
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        returned_token = data['data']['telegram']['botToken']
        self.assertEqual(returned_token, 'my-secret-bot-token-12345')
    
    def test_config_get_returns_unmasked_sensitive_fields(self):
        """Test that GET config returns unmasked values."""
        config = self.store.get_config()
        config['telegram']['botToken'] = 'my-secret-bot-token-12345'
        self.store.update_config(config)
        
        response = self.client.get('/api/config',
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        returned_token = data['data']['telegram']['botToken']
        self.assertEqual(returned_token, 'my-secret-bot-token-12345')
    
    def test_config_has_valid_session_flag(self):
        """Test that config includes hasValidSession flag."""
        response = self.client.get('/api/config',
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        # Check that flag exists
        self.assertIn('cloud115', data['data'])
        self.assertIn('hasValidSession', data['data']['cloud115'])
        # Should be false without stored cookies
        self.assertFalse(data['data']['cloud115']['hasValidSession'])


if __name__ == '__main__':
    unittest.main()
