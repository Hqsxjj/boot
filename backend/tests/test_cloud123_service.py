import unittest
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.cloud123_service import Cloud123Service
from services.secret_store import SecretStore
from models.database import init_db, get_session_factory


class TestCloud123Service(unittest.TestCase):
    """Test Cloud123Service functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        
        # Override database URL before creating db
        os.environ['DATABASE_URL'] = f'sqlite:///{self.temp_db.name}'
        os.environ['SECRETS_ENCRYPTION_KEY'] = 'test-encryption-key-32-chars-long!!'
        
        self.engine = init_db()
        self.session_factory = get_session_factory(self.engine)
        self.secret_store = SecretStore(self.session_factory)
        self.service = Cloud123Service(self.secret_store)
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_list_directory_no_credentials(self):
        """Test listing directory without credentials fails gracefully."""
        result = self.service.list_directory('/')
        
        self.assertFalse(result.get('success'))
        self.assertIn('error', result)
    
    @patch.object(Cloud123Service, '_get_authenticated_client')
    def test_list_directory_success(self, mock_get_client):
        """Test listing directory with mocked client."""
        # Create mock entries with proper attribute setup
        mock_entry1 = Mock()
        mock_entry1.configure_mock(
            id='file-1',
            name='Document.pdf',
            is_dir=False,
            is_directory=False,
            timestamp=1609459200
        )
        
        mock_entry2 = Mock()
        mock_entry2.configure_mock(
            id='dir-1',
            name='Downloads',
            is_dir=True,
            is_directory=True,
            timestamp=1609459200
        )
        
        mock_client = Mock()
        mock_client.list_files.return_value = [mock_entry1, mock_entry2]
        mock_get_client.return_value = mock_client
        
        result = self.service.list_directory('/')
        
        self.assertTrue(result.get('success'))
        self.assertEqual(len(result['data']), 2)
        
        # Check first entry
        self.assertEqual(result['data'][0]['id'], 'file-1')
        self.assertEqual(result['data'][0]['name'], 'Document.pdf')
        self.assertFalse(result['data'][0]['children'])
        self.assertEqual(result['data'][0]['date'], '2021-01-01')
        
        # Check second entry
        self.assertEqual(result['data'][1]['id'], 'dir-1')
        self.assertEqual(result['data'][1]['name'], 'Downloads')
        self.assertTrue(result['data'][1]['children'])
    
    @patch.object(Cloud123Service, '_get_authenticated_client')
    def test_rename_file_success(self, mock_get_client):
        """Test renaming a file."""
        mock_client = Mock()
        mock_client.rename = Mock()
        mock_get_client.return_value = mock_client
        
        result = self.service.rename_file('file-123', 'NewName.pdf')
        
        self.assertTrue(result.get('success'))
        self.assertEqual(result['data']['fileId'], 'file-123')
        self.assertEqual(result['data']['newName'], 'NewName.pdf')
        mock_client.rename.assert_called_once_with('file-123', 'NewName.pdf')
    
    @patch.object(Cloud123Service, '_get_authenticated_client')
    def test_move_file_success(self, mock_get_client):
        """Test moving a file."""
        mock_client = Mock()
        mock_client.move = Mock()
        mock_get_client.return_value = mock_client
        
        result = self.service.move_file('file-123', '/destination')
        
        self.assertTrue(result.get('success'))
        self.assertEqual(result['data']['fileId'], 'file-123')
        self.assertEqual(result['data']['targetDirId'], '/destination')
        mock_client.move.assert_called_once_with('file-123', '/destination')
    
    @patch.object(Cloud123Service, '_get_authenticated_client')
    def test_delete_file_success(self, mock_get_client):
        """Test deleting a file."""
        mock_client = Mock()
        mock_client.delete = Mock()
        mock_get_client.return_value = mock_client
        
        result = self.service.delete_file('file-123')
        
        self.assertTrue(result.get('success'))
        self.assertEqual(result['data']['fileId'], 'file-123')
        mock_client.delete.assert_called_once_with('file-123')
    
    @patch.object(Cloud123Service, '_get_authenticated_client')
    def test_get_download_link_success(self, mock_get_client):
        """Test getting download link."""
        mock_client = Mock()
        mock_client.get_download_url.return_value = 'https://example.com/download?token=abc123'
        mock_get_client.return_value = mock_client
        
        result = self.service.get_download_link('file-123')
        
        self.assertTrue(result.get('success'))
        self.assertEqual(result['data']['fileId'], 'file-123')
        self.assertEqual(result['data']['url'], 'https://example.com/download?token=abc123')
    
    @patch.object(Cloud123Service, '_get_authenticated_client')
    def test_create_offline_task_success(self, mock_get_client):
        """Test creating an offline task."""
        mock_client = Mock()
        mock_client.add_offline_task.return_value = {'task_id': 'task-123', 'status': 'pending'}
        mock_get_client.return_value = mock_client
        
        result = self.service.create_offline_task('https://example.com/file.zip', '/')
        
        self.assertTrue(result.get('success'))
        self.assertEqual(result['data']['p123TaskId'], 'task-123')
        self.assertEqual(result['data']['sourceUrl'], 'https://example.com/file.zip')
        self.assertEqual(result['data']['saveDirId'], '/')
    
    @patch.object(Cloud123Service, '_get_authenticated_client')
    def test_get_offline_task_status_success(self, mock_get_client):
        """Test getting offline task status."""
        mock_task = Mock()
        mock_task.task_id = 'task-123'
        mock_task.status = '2'  # completed
        mock_task.progress = 100
        mock_task.speed = 1024000
        
        mock_client = Mock()
        mock_client.list_offline_tasks.return_value = [mock_task]
        mock_get_client.return_value = mock_client
        
        result = self.service.get_offline_task_status('task-123')
        
        self.assertTrue(result.get('success'))
        self.assertEqual(result['data']['status'], 'completed')
        self.assertEqual(result['data']['progress'], 100)
        self.assertEqual(result['data']['speed'], 1024000.0)
    
    @patch.object(Cloud123Service, '_get_authenticated_client')
    def test_get_offline_task_status_not_found(self, mock_get_client):
        """Test getting status of non-existent task."""
        mock_client = Mock()
        mock_client.list_offline_tasks.return_value = []
        mock_get_client.return_value = mock_client
        
        result = self.service.get_offline_task_status('non-existent')
        
        self.assertFalse(result.get('success'))
        self.assertIn('not found', result.get('error', '').lower())
    
    def test_get_session_metadata_empty(self):
        """Test getting session metadata when none exists."""
        metadata = self.service.get_session_metadata()
        
        self.assertEqual(metadata, {})
    
    def test_get_session_metadata_exists(self):
        """Test getting session metadata when it exists."""
        stored_metadata = {'login_method': 'oauth', 'logged_in_at': '2024-01-01T12:00:00'}
        self.secret_store.set_secret('cloud123_session_metadata', json.dumps(stored_metadata))
        
        metadata = self.service.get_session_metadata()
        
        self.assertEqual(metadata['login_method'], 'oauth')
        self.assertIn('logged_in_at', metadata)


if __name__ == '__main__':
    unittest.main()
