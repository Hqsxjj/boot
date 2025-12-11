import unittest
import json
import tempfile
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import create_app
from persistence.store import DataStore
from services.offline_tasks import OfflineTaskService
from models.offline_task import TaskStatus


class TestOfflineTaskAPI(unittest.TestCase):
    """Test offline task API endpoints."""
    
    def setUp(self):
        """Set up test client and temporary data file."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        
        # Set up database in memory for testing
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
        
        # Set up admin credentials for auth
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
    
    def test_create_task_success(self):
        """Test creating an offline task successfully."""
        response = self.client.post('/api/115/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveCid': '123456789'
            },
            headers=self.headers,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertEqual(data['data']['status'], 'pending')
        self.assertEqual(data['data']['progress'], 0)
        self.assertEqual(data['data']['sourceUrl'], 'https://example.com/file.zip')
        self.assertEqual(data['data']['saveCid'], '123456789')
    
    def test_create_task_missing_sourceurl(self):
        """Test creating task without source URL."""
        response = self.client.post('/api/115/offline/tasks',
            json={
                'saveCid': '123456789'
            },
            headers=self.headers,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('error', data)
    
    def test_create_task_missing_savecid(self):
        """Test creating task without save CID."""
        response = self.client.post('/api/115/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip'
            },
            headers=self.headers,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_create_task_without_auth(self):
        """Test creating task without authentication."""
        response = self.client.post('/api/115/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveCid': '123456789'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)
    
    def test_list_tasks_empty(self):
        """Test listing tasks when none exist."""
        response = self.client.get('/api/115/offline/tasks',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']['tasks']), 0)
        self.assertEqual(data['data']['total'], 0)
    
    def test_list_tasks_with_data(self):
        """Test listing tasks with data."""
        # Create a task
        create_response = self.client.post('/api/115/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveCid': '123456789'
            },
            headers=self.headers,
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['data']['id']
        
        # List tasks
        response = self.client.get('/api/115/offline/tasks',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']['tasks']), 1)
        self.assertEqual(data['data']['total'], 1)
        self.assertEqual(data['data']['tasks'][0]['id'], task_id)
    
    def test_list_tasks_with_pagination(self):
        """Test listing tasks with pagination."""
        # Create multiple tasks
        for i in range(5):
            self.client.post('/api/115/offline/tasks',
                json={
                    'sourceUrl': f'https://example.com/file{i}.zip',
                    'saveCid': '123456789'
                },
                headers=self.headers,
                content_type='application/json'
            )
        
        # List with limit
        response = self.client.get('/api/115/offline/tasks?limit=2&offset=0',
            headers=self.headers
        )
        
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['tasks']), 2)
        self.assertEqual(data['data']['total'], 5)
        
        # List with offset
        response = self.client.get('/api/115/offline/tasks?limit=2&offset=2',
            headers=self.headers
        )
        
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['tasks']), 2)
    
    def test_list_tasks_filter_by_status(self):
        """Test filtering tasks by status."""
        # Create a task
        create_response = self.client.post('/api/115/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveCid': '123456789'
            },
            headers=self.headers,
            content_type='application/json'
        )
        
        # Filter by pending status
        response = self.client.get('/api/115/offline/tasks?status=pending',
            headers=self.headers
        )
        
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['tasks']), 1)
        
        # Filter by downloading status (should be empty)
        response = self.client.get('/api/115/offline/tasks?status=downloading',
            headers=self.headers
        )
        
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['tasks']), 0)
    
    def test_get_task(self):
        """Test getting a single task."""
        # Create a task
        create_response = self.client.post('/api/115/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveCid': '123456789'
            },
            headers=self.headers,
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['data']['id']
        
        # Get the task
        response = self.client.get(f'/api/115/offline/tasks/{task_id}',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['id'], task_id)
    
    def test_get_nonexistent_task(self):
        """Test getting a nonexistent task."""
        response = self.client.get('/api/115/offline/tasks/nonexistent',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_cancel_task(self):
        """Test cancelling a task."""
        # Create a task
        create_response = self.client.post('/api/115/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveCid': '123456789'
            },
            headers=self.headers,
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['data']['id']
        
        # Cancel the task
        response = self.client.patch(f'/api/115/offline/tasks/{task_id}',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['status'], 'cancelled')
    
    def test_delete_task(self):
        """Test deleting a task."""
        # Create a task
        create_response = self.client.post('/api/115/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveCid': '123456789'
            },
            headers=self.headers,
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['data']['id']
        
        # Delete the task
        response = self.client.delete(f'/api/115/offline/tasks/{task_id}',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # Verify it's deleted
        response = self.client.get(f'/api/115/offline/tasks/{task_id}',
            headers=self.headers
        )
        self.assertEqual(response.status_code, 404)
    
    def test_retry_task(self):
        """Test retrying a failed task."""
        # Create a task
        create_response = self.client.post('/api/115/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveCid': '123456789'
            },
            headers=self.headers,
            content_type='application/json'
        )
        task_id = json.loads(create_response.data)['data']['id']
        
        # Manually set task to failed status via service
        task = self.app.offline_task_service.get_task(task_id)
        session = self.app.session_factory()
        task.status = TaskStatus.FAILED
        session.merge(task)
        session.commit()
        session.close()
        
        # Retry the task
        response = self.client.post(f'/api/115/offline/tasks/{task_id}/retry',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['status'], 'pending')
        self.assertEqual(data['data']['progress'], 0)
    
    def test_list_with_refresh(self):
        """Test listing tasks with refresh parameter."""
        # Create a task
        self.client.post('/api/115/offline/tasks',
            json={
                'sourceUrl': 'https://example.com/file.zip',
                'saveCid': '123456789'
            },
            headers=self.headers,
            content_type='application/json'
        )
        
        # List with refresh (should sync before responding)
        response = self.client.get('/api/115/offline/tasks?refresh=true',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])


class TestOfflineTaskService(unittest.TestCase):
    """Test offline task service."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        
        os.environ['DATA_PATH'] = self.temp_file.name
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        
        self.app = create_app({
            'TESTING': True,
            'JWT_SECRET_KEY': 'test-secret',
            'SECRET_KEY': 'test-secret'
        })
        
        self.store = DataStore(self.temp_file.name)
        self.service = self.app.offline_task_service
    
    def tearDown(self):
        """Clean up."""
        if self.app.task_poller:
            self.app.task_poller.stop()
        
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_create_task(self):
        """Test creating a task via service."""
        result = self.service.create_task(
            source_url='https://example.com/file.zip',
            save_cid='123456789',
            requested_by='user1',
            requested_chat='chat1'
        )
        
        self.assertTrue(result['success'])
        self.assertIn('data', result)
        self.assertEqual(result['data']['status'], 'pending')
    
    def test_list_tasks(self):
        """Test listing tasks via service."""
        # Create a task
        self.service.create_task(
            source_url='https://example.com/file.zip',
            save_cid='123456789',
            requested_by='user1',
            requested_chat='chat1'
        )
        
        result = self.service.list_tasks()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['total'], 1)
        self.assertEqual(len(result['data']['tasks']), 1)
    
    def test_sync_all(self):
        """Test syncing all tasks."""
        # Create tasks
        self.service.create_task(
            source_url='https://example.com/file1.zip',
            save_cid='123456789',
            requested_by='user1',
            requested_chat='chat1'
        )
        self.service.create_task(
            source_url='https://example.com/file2.zip',
            save_cid='123456789',
            requested_by='user2',
            requested_chat='chat2'
        )
        
        result = self.service.sync_all()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total'], 2)
    
    def test_cancel_task(self):
        """Test cancelling a task via service."""
        # Create a task
        create_result = self.service.create_task(
            source_url='https://example.com/file.zip',
            save_cid='123456789',
            requested_by='user1',
            requested_chat='chat1'
        )
        task_id = create_result['data']['id']
        
        # Cancel it
        result = self.service.cancel_task(task_id)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['status'], 'cancelled')
    
    def test_retry_task(self):
        """Test retrying a task via service."""
        # Create a task
        create_result = self.service.create_task(
            source_url='https://example.com/file.zip',
            save_cid='123456789',
            requested_by='user1',
            requested_chat='chat1'
        )
        task_id = create_result['data']['id']
        
        # Set to failed
        task = self.service.get_task(task_id)
        session = self.app.session_factory()
        task.status = TaskStatus.FAILED
        session.merge(task)
        session.commit()
        session.close()
        
        # Retry it
        result = self.service.retry_task(task_id)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['status'], 'pending')
    
    def test_delete_task(self):
        """Test deleting a task via service."""
        # Create a task
        create_result = self.service.create_task(
            source_url='https://example.com/file.zip',
            save_cid='123456789',
            requested_by='user1',
            requested_chat='chat1'
        )
        task_id = create_result['data']['id']
        
        # Delete it
        result = self.service.delete_task(task_id)
        
        self.assertTrue(result['success'])
        
        # Verify it's gone
        task = self.service.get_task(task_id)
        self.assertIsNone(task)


if __name__ == '__main__':
    unittest.main()
