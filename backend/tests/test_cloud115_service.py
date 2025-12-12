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
from services.secret_store import SecretStore
from services.cloud115_service import Cloud115Service


class TestCloud115Service(unittest.TestCase):
    """Test Cloud115Service class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        
        os.environ['DATABASE_URL'] = f'sqlite:///{self.temp_db.name}'
        os.environ['SECRETS_ENCRYPTION_KEY'] = 'test-encryption-key-32-chars-long!!'
        
        engine = init_db()
        session_factory = get_session_factory(engine)
        self.secret_store = SecretStore(session_factory)
        self.service = Cloud115Service(self.secret_store)
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_list_directory_no_cookies(self):
        """Test listing directory without cookies stored."""
        result = self.service.list_directory('0')
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    @patch('services.cloud115_service.Cloud115Service._get_authenticated_client')
    def test_list_directory_with_client(self, mock_client):
        """Test listing directory with mocked p115client."""
        # Set up cookies
        self.secret_store.set_secret('cloud115_cookies', json.dumps({'UID': 'test123'}))
        
        # Mock client
        mock_fs = Mock()
        mock_entry1 = Mock()
        mock_entry1.id = '101'
        mock_entry1.name = '电影 (Movies)'
        mock_entry1.is_directory = True
        mock_entry1.timestamp = 1698192000
        
        mock_entry2 = Mock()
        mock_entry2.id = '102'
        mock_entry2.name = '电视剧 (TV Shows)'
        mock_entry2.is_directory = True
        mock_entry2.timestamp = 1698278400
        
        mock_fs.listdir.return_value = [mock_entry1, mock_entry2]
        
        mock_client_instance = Mock()
        mock_client_instance.fs = mock_fs
        mock_client.return_value = mock_client_instance
        
        result = self.service.list_directory('0')
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['data']), 2)
        self.assertEqual(result['data'][0]['id'], '101')
        self.assertEqual(result['data'][0]['name'], '电影 (Movies)')
        self.assertTrue(result['data'][0]['children'])
    
    @patch('services.cloud115_service.Cloud115Service._get_authenticated_client')
    def test_rename_file(self, mock_client):
        """Test renaming a file."""
        self.secret_store.set_secret('cloud115_cookies', json.dumps({'UID': 'test123'}))
        
        mock_fs = Mock()
        mock_fs.rename = Mock()
        
        mock_client_instance = Mock()
        mock_client_instance.fs = mock_fs
        mock_client.return_value = mock_client_instance
        
        result = self.service.rename_file('12345', 'new_name.txt')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['fileId'], '12345')
        self.assertEqual(result['data']['newName'], 'new_name.txt')
        mock_fs.rename.assert_called_once_with('12345', 'new_name.txt')
    
    @patch('services.cloud115_service.Cloud115Service._get_authenticated_client')
    def test_move_file(self, mock_client):
        """Test moving a file."""
        self.secret_store.set_secret('cloud115_cookies', json.dumps({'UID': 'test123'}))
        
        mock_fs = Mock()
        mock_fs.move = Mock()
        
        mock_client_instance = Mock()
        mock_client_instance.fs = mock_fs
        mock_client.return_value = mock_client_instance
        
        result = self.service.move_file('12345', '67890')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['fileId'], '12345')
        self.assertEqual(result['data']['targetCid'], '67890')
        mock_fs.move.assert_called_once_with('12345', '67890')
    
    @patch('services.cloud115_service.Cloud115Service._get_authenticated_client')
    def test_delete_file(self, mock_client):
        """Test deleting a file."""
        self.secret_store.set_secret('cloud115_cookies', json.dumps({'UID': 'test123'}))
        
        mock_fs = Mock()
        mock_fs.delete = Mock()
        
        mock_client_instance = Mock()
        mock_client_instance.fs = mock_fs
        mock_client.return_value = mock_client_instance
        
        result = self.service.delete_file('12345')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['fileId'], '12345')
        mock_fs.delete.assert_called_once_with('12345')
    
    @patch('services.cloud115_service.Cloud115Service._get_authenticated_client')
    def test_get_download_link(self, mock_client):
        """Test getting download link."""
        self.secret_store.set_secret('cloud115_cookies', json.dumps({'UID': 'test123'}))
        
        mock_fs = Mock()
        mock_fs.get_url = Mock(return_value='https://example.com/download/file.zip')
        
        mock_client_instance = Mock()
        mock_client_instance.fs = mock_fs
        mock_client.return_value = mock_client_instance
        
        result = self.service.get_download_link('12345')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['fileId'], '12345')
        self.assertEqual(result['data']['url'], 'https://example.com/download/file.zip')
    
    @patch('services.cloud115_service.Cloud115Service._get_authenticated_client')
    def test_create_offline_task(self, mock_client):
        """Test creating offline task."""
        self.secret_store.set_secret('cloud115_cookies', json.dumps({'UID': 'test123'}))
        
        mock_offline = Mock()
        mock_offline.add_url = Mock(return_value={'task_id': 'task_12345'})
        
        mock_client_instance = Mock()
        mock_client_instance.offline = mock_offline
        mock_client.return_value = mock_client_instance
        
        result = self.service.create_offline_task('https://example.com/file.zip', '67890')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['p115TaskId'], 'task_12345')
        self.assertEqual(result['data']['sourceUrl'], 'https://example.com/file.zip')
        self.assertEqual(result['data']['saveCid'], '67890')
    
    @patch('services.cloud115_service.Cloud115Service._get_authenticated_client')
    def test_get_offline_task_status(self, mock_client):
        """Test getting offline task status."""
        self.secret_store.set_secret('cloud115_cookies', json.dumps({'UID': 'test123'}))
        
        mock_task = {
            'task_id': 'task_12345',
            'status': '1',  # downloading
            'progress': 0.45,
            'speed': 1024000
        }
        
        mock_offline = Mock()
        mock_offline.list = Mock(return_value=[mock_task])
        
        mock_client_instance = Mock()
        mock_client_instance.offline = mock_offline
        mock_client.return_value = mock_client_instance
        
        result = self.service.get_offline_task_status('task_12345')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['status'], 'downloading')
        self.assertEqual(result['data']['progress'], 45)
        self.assertEqual(result['data']['speed'], 1024000)


class TestCloud115Endpoints(unittest.TestCase):
    """Test cloud115 blueprint endpoints."""
    
    def setUp(self):
        """Set up test client and temporary data file."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        
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
    
    def test_list_directories_without_auth(self):
        """Test listing directories without authentication."""
        response = self.client.get('/api/115/directories')
        
        self.assertEqual(response.status_code, 401)
    
    def test_list_directories_no_cookies(self):
        """Test listing directories without cookies stored."""
        response = self.client.get('/api/115/directories?cid=0',
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    @patch('services.cloud115_service.Cloud115Service._get_authenticated_client')
    def test_list_directories_success(self, mock_client):
        """Test listing directories successfully."""
        # Set up cookies
        self.app.secret_store.set_secret('cloud115_cookies', json.dumps({'UID': 'test123'}))
        
        # Mock client
        mock_fs = Mock()
        mock_entry = Mock()
        mock_entry.id = '101'
        mock_entry.name = '电影'
        mock_entry.is_directory = True
        mock_entry.timestamp = 1698192000
        
        mock_fs.listdir.return_value = [mock_entry]
        
        mock_client_instance = Mock()
        mock_client_instance.fs = mock_fs
        mock_client.return_value = mock_client_instance
        
        response = self.client.get('/api/115/directories?cid=0',
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['id'], '101')
        self.assertEqual(data['data'][0]['name'], '电影')
        self.assertTrue(data['data'][0]['children'])
    
    @patch('services.cloud115_service.Cloud115Service._get_authenticated_client')
    def test_rename_file_success(self, mock_client):
        """Test renaming a file successfully."""
        self.app.secret_store.set_secret('cloud115_cookies', json.dumps({'UID': 'test123'}))
        
        mock_fs = Mock()
        mock_fs.rename = Mock()
        
        mock_client_instance = Mock()
        mock_client_instance.fs = mock_fs
        mock_client.return_value = mock_client_instance
        
        response = self.client.post('/api/115/files/rename',
            json={
                'fileId': '12345',
                'newName': 'new_file.txt'
            },
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['fileId'], '12345')
    
    def test_rename_file_missing_params(self):
        """Test renaming without required parameters."""
        response = self.client.post('/api/115/files/rename',
            json={
                'fileId': '12345'
            },
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    @patch('services.cloud115_service.Cloud115Service._get_authenticated_client')
    def test_move_file_success(self, mock_client):
        """Test moving a file successfully."""
        self.app.secret_store.set_secret('cloud115_cookies', json.dumps({'UID': 'test123'}))
        
        mock_fs = Mock()
        mock_fs.move = Mock()
        
        mock_client_instance = Mock()
        mock_client_instance.fs = mock_fs
        mock_client.return_value = mock_client_instance
        
        response = self.client.post('/api/115/files/move',
            json={
                'fileId': '12345',
                'targetCid': '67890'
            },
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
    
    @patch('services.cloud115_service.Cloud115Service._get_authenticated_client')
    def test_delete_file_success(self, mock_client):
        """Test deleting a file successfully."""
        self.app.secret_store.set_secret('cloud115_cookies', json.dumps({'UID': 'test123'}))
        
        mock_fs = Mock()
        mock_fs.delete = Mock()
        
        mock_client_instance = Mock()
        mock_client_instance.fs = mock_fs
        mock_client.return_value = mock_client_instance
        
        response = self.client.delete('/api/115/files',
            json={
                'fileId': '12345'
            },
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
    
    @patch('services.cloud115_service.Cloud115Service._get_authenticated_client')
    def test_create_offline_task_via_files_endpoint(self, mock_client):
        """Test creating offline task via /api/115/files/offline."""
        self.app.secret_store.set_secret('cloud115_cookies', json.dumps({'UID': 'test123'}))
        
        mock_offline = Mock()
        mock_offline.add_url = Mock(return_value={'task_id': 'task_12345'})
        
        mock_client_instance = Mock()
        mock_client_instance.offline = mock_offline
        mock_client.return_value = mock_client_instance
        
        response = self.client.post('/api/115/files/offline',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveCid': '67890'
            },
            headers=self.auth_header,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertTrue(data['success'])


class TestOfflineTaskSync(unittest.TestCase):
    """Test offline task sync with 115 API."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        
        os.environ['DATA_PATH'] = self.temp_file.name
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        os.environ['TESTING'] = 'true'
        
        self.app = create_app({
            'TESTING': True,
            'JWT_SECRET_KEY': 'test-secret',
            'SECRET_KEY': 'test-secret'
        })
        
        self.client = self.app.test_client()
        self.store = DataStore(self.temp_file.name)
        
        # Set up admin credentials
        self.store.update_admin_password(generate_password_hash('testpass123'))
        
        # Get JWT token
        login_response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'testpass123'},
            content_type='application/json'
        )
        self.token = json.loads(login_response.data)['data']['token']
        self.headers = {'Authorization': f'Bearer {self.token}'}
    
    def tearDown(self):
        """Clean up temporary file."""
        if self.app.task_poller:
            self.app.task_poller.stop()
        
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    @patch('services.cloud115_service.Cloud115Service.get_offline_task_status')
    def test_sync_updates_task_status(self, mock_get_status):
        """Test that sync updates task status from 115 API."""
        # Create a task with p115_task_id
        from models.offline_task import TaskStatus
        
        create_response = self.client.post('/api/115/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveCid': '123456789'
            },
            headers=self.headers,
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['data']['id']
        
        # Manually set p115_task_id
        task = self.app.offline_task_service.get_task(task_id)
        session = self.app.session_factory()
        task.p115_task_id = 'p115_task_123'
        session.merge(task)
        session.commit()
        session.close()
        
        # Mock status response
        mock_get_status.return_value = {
            'success': True,
            'data': {
                'status': 'downloading',
                'progress': 50,
                'speed': 1024000
            }
        }
        
        # Sync tasks
        result = self.app.offline_task_service.sync_all()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['synced'], 1)
        
        # Verify task was updated
        updated_task = self.app.offline_task_service.get_task(task_id)
        self.assertEqual(updated_task.status, TaskStatus.DOWNLOADING)
        self.assertEqual(updated_task.progress, 50)
        self.assertEqual(updated_task.speed, 1024000)


if __name__ == '__main__':
    unittest.main()
