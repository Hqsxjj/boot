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


class TestCloud123Blueprint(unittest.TestCase):
    """Test 123 cloud blueprint endpoints."""
    
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
    
    def test_oauth_login_success(self):
        """Test OAuth login credentials storage."""
        response = self.client.post('/api/123/login/oauth',
            json={
                'clientId': 'test-client-id',
                'clientSecret': 'test-client-secret'
            },
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('message', data['data'])
    
    def test_oauth_login_missing_credentials(self):
        """Test OAuth login with missing credentials."""
        response = self.client.post('/api/123/login/oauth',
            json={'clientId': 'test-client-id'},
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('clientSecret', data['error'])
    
    def test_oauth_login_without_auth(self):
        """Test OAuth login without authentication."""
        response = self.client.post('/api/123/login/oauth',
            json={
                'clientId': 'test-client-id',
                'clientSecret': 'test-client-secret'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)
    
    def test_ingest_cookies_success(self):
        """Test ingesting cookies."""
        cookies = {
            'sessionId': 'test-session',
            'token': 'test-token',
            'userId': 'user-123'
        }
        
        response = self.client.post('/api/123/login/cookie',
            json={'cookies': cookies},
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('message', data['data'])
    
    def test_ingest_cookies_as_json_string(self):
        """Test ingesting cookies provided as JSON string."""
        cookies_str = json.dumps({
            'sessionId': 'test-session',
            'token': 'test-token'
        })
        
        response = self.client.post('/api/123/login/cookie',
            json={'cookies': cookies_str},
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
    
    def test_ingest_cookies_missing_cookies(self):
        """Test ingesting without cookies parameter."""
        response = self.client.post('/api/123/login/cookie',
            json={},
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('Cookies are required', data['error'])
    
    def test_ingest_cookies_without_auth(self):
        """Test ingesting cookies without authentication."""
        response = self.client.post('/api/123/login/cookie',
            json={'cookies': {}},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)
    
    def test_get_session_health_no_session(self):
        """Test session health check with no configured session."""
        response = self.client.get('/api/123/session',
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertFalse(data['data']['hasValidSession'])
    
    def test_get_session_health_with_cookies(self):
        """Test session health check with stored cookies."""
        # Store cookies first
        self.app.secret_store.set_secret('cloud123_cookies', json.dumps({
            'sessionId': 'test-session'
        }))
        
        response = self.client.get('/api/123/session',
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertTrue(data['data']['hasValidSession'])
    
    def test_get_session_health_without_auth(self):
        """Test session health check without authentication."""
        response = self.client.get('/api/123/session')
        
        self.assertEqual(response.status_code, 401)
    
    @patch('services.cloud123_service.Cloud123Service._get_authenticated_client')
    def test_list_directories_success(self, mock_get_client):
        """Test listing directories."""
        mock_entry = Mock()
        mock_entry.id = 'dir-1'
        mock_entry.name = 'Downloads'
        mock_entry.is_dir = True
        mock_entry.timestamp = 1609459200
        
        mock_client = Mock()
        mock_client.list_files.return_value = [mock_entry]
        mock_get_client.return_value = mock_client
        
        response = self.client.get('/api/123/directories?dirId=/',
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['id'], 'dir-1')
        self.assertEqual(data['data'][0]['name'], 'Downloads')
    
    @patch('services.cloud123_service.Cloud123Service._get_authenticated_client')
    def test_list_directories_no_credentials(self, mock_get_client):
        """Test listing directories without credentials."""
        mock_get_client.side_effect = ValueError('No 123 token or cookies found')
        
        response = self.client.get('/api/123/directories',
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_list_directories_without_auth(self):
        """Test listing directories without authentication."""
        response = self.client.get('/api/123/directories')
        
        self.assertEqual(response.status_code, 401)
    
    @patch('services.cloud123_service.Cloud123Service._get_authenticated_client')
    def test_rename_file_success(self, mock_get_client):
        """Test renaming a file."""
        mock_client = Mock()
        mock_client.rename = Mock()
        mock_get_client.return_value = mock_client
        
        response = self.client.post('/api/123/files/rename',
            json={
                'fileId': 'file-123',
                'newName': 'NewName.pdf'
            },
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['fileId'], 'file-123')
        self.assertEqual(data['data']['newName'], 'NewName.pdf')
    
    def test_rename_file_missing_params(self):
        """Test renaming without required parameters."""
        response = self.client.post('/api/123/files/rename',
            json={'fileId': 'file-123'},
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('newName', data['error'])
    
    @patch('services.cloud123_service.Cloud123Service._get_authenticated_client')
    def test_move_file_success(self, mock_get_client):
        """Test moving a file."""
        mock_client = Mock()
        mock_client.move = Mock()
        mock_get_client.return_value = mock_client
        
        response = self.client.post('/api/123/files/move',
            json={
                'fileId': 'file-123',
                'targetDirId': '/destination'
            },
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['targetDirId'], '/destination')
    
    def test_move_file_missing_params(self):
        """Test moving without required parameters."""
        response = self.client.post('/api/123/files/move',
            json={'fileId': 'file-123'},
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('targetDirId', data['error'])
    
    @patch('services.cloud123_service.Cloud123Service._get_authenticated_client')
    def test_delete_file_success(self, mock_get_client):
        """Test deleting a file."""
        mock_client = Mock()
        mock_client.delete = Mock()
        mock_get_client.return_value = mock_client
        
        response = self.client.delete('/api/123/files',
            json={'fileId': 'file-123'},
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['fileId'], 'file-123')
    
    def test_delete_file_missing_file_id(self):
        """Test deleting without fileId."""
        response = self.client.delete('/api/123/files',
            json={},
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('fileId', data['error'])
    
    @patch('services.cloud123_service.Cloud123Service._get_authenticated_client')
    def test_create_offline_task_success(self, mock_get_client):
        """Test creating offline task."""
        mock_client = Mock()
        mock_client.add_offline_task.return_value = {'task_id': 'task-123'}
        mock_get_client.return_value = mock_client
        
        response = self.client.post('/api/123/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveDirId': '/'
            },
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['p123TaskId'], 'task-123')
        self.assertEqual(data['data']['sourceUrl'], 'https://example.com/file.zip')
    
    def test_create_offline_task_missing_params(self):
        """Test creating offline task without required parameters."""
        response = self.client.post('/api/123/offline/tasks',
            json={'sourceUrl': 'https://example.com/file.zip'},
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('saveDirId', data['error'])
    
    def test_create_offline_task_without_auth(self):
        """Test creating offline task without authentication."""
        response = self.client.post('/api/123/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveDirId': '/'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)
    
    @patch('services.cloud123_service.Cloud123Service._get_authenticated_client')
    def test_get_offline_task_status_success(self, mock_get_client):
        """Test getting offline task status."""
        mock_task = Mock()
        mock_task.task_id = 'task-123'
        mock_task.status = '2'
        mock_task.progress = 50
        mock_task.speed = 512000
        
        mock_client = Mock()
        mock_client.list_offline_tasks.return_value = [mock_task]
        mock_get_client.return_value = mock_client
        
        response = self.client.get('/api/123/offline/tasks/task-123',
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['status'], 'completed')
        self.assertEqual(data['data']['progress'], 50)
    
    def test_get_offline_task_without_auth(self):
        """Test getting offline task status without authentication."""
        response = self.client.get('/api/123/offline/tasks/task-123')
        
        self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()
