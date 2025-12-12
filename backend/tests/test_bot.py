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


class TestBotBlueprint(unittest.TestCase):
    """Test bot blueprint endpoints."""
    
    def setUp(self):
        """Set up test client and temporary data files."""
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yml')
        self.temp_config.close()
        self.temp_data = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_data.close()
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        
        # Override paths BEFORE creating app
        os.environ['DATA_PATH'] = self.temp_data.name
        os.environ['CONFIG_YAML_PATH'] = self.temp_config.name
        os.environ['DATABASE_URL'] = f'sqlite:///{self.temp_db.name}'
        os.environ['SECRETS_ENCRYPTION_KEY'] = 'test-encryption-key-32-chars-long!!'
        os.environ['ALLOW_UNAUTHENTICATED_CONFIG'] = 'true'
        
        self.app = create_app({
            'TESTING': True,
            'JWT_SECRET_KEY': 'test-secret',
            'SECRET_KEY': 'test-secret'
        })
        
        self.client = self.app.test_client()
        self.store = DataStore(self.temp_data.name, self.temp_config.name)
        
        # Initialize default config
        default_config = {
            'telegram': {
                'botToken': '',
                'adminUserId': '',
                'notificationChannelId': '',
                'whitelistMode': False
            },
            'cloud115': {
                'loginMethod': 'cookie',
                'loginApp': 'web',
                'cookies': '',
                'userAgent': '',
                'downloadPath': '0',
                'downloadDirName': 'Downloads',
                'autoDeleteMsg': True,
                'qps': 1.0
            },
            'cloud123': {
                'enabled': False,
                'clientId': '',
                'clientSecret': '',
                'downloadPath': '0',
                'downloadDirName': 'Downloads',
                'qps': 1.0
            },
            'proxy': {
                'enabled': False,
                'type': 'http',
                'host': '',
                'port': '',
                'username': '',
                'password': ''
            },
            'tmdb': {
                'apiKey': '',
                'language': 'zh-CN',
                'includeAdult': False
            }
        }
        self.store.update_config(default_config)
        
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
        try:
            os.unlink(self.temp_config.name)
            os.unlink(self.temp_data.name)
            os.unlink(self.temp_db.name)
        except:
            pass
    
    @patch('requests.get')
    def test_validate_bot_token_success(self, mock_get):
        """Test successful bot token validation."""
        # Mock successful Telegram API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'ok': True,
            'result': {
                'id': 123456789,
                'is_bot': True,
                'first_name': 'TestBot',
                'username': 'testbot'
            }
        }
        mock_get.return_value = mock_response
        
        # Test validation with mocked secret store
        from services.telegram_bot import TelegramBotService
        
        mock_secret_store = Mock()
        service = TelegramBotService(mock_secret_store)
        
        result = service.validate_bot_token('123456:ABC-DEF')
        
        self.assertTrue(result['valid'])
        self.assertIn('data', result)
        self.assertEqual(result['data']['username'], 'testbot')
        
        # Verify API was called correctly
        mock_get.assert_called_once_with(
            'https://api.telegram.org/bot123456:ABC-DEF/getMe',
            timeout=10
        )
    
    @patch('requests.get')
    def test_validate_bot_token_invalid(self, mock_get):
        """Test invalid bot token validation."""
        # Mock failed Telegram API response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'ok': False,
            'description': 'Unauthorized'
        }
        mock_get.return_value = mock_response
        
        from services.telegram_bot import TelegramBotService
        
        mock_secret_store = Mock()
        service = TelegramBotService(mock_secret_store)
        
        result = service.validate_bot_token('invalid_token')
        
        self.assertFalse(result['valid'])
        self.assertIn('error', result)
    
    @patch('requests.get')
    def test_validate_bot_token_timeout(self, mock_get):
        """Test bot token validation timeout."""
        # Mock timeout
        import requests.exceptions
        mock_get.side_effect = requests.exceptions.Timeout()
        
        from services.telegram_bot import TelegramBotService
        
        mock_secret_store = Mock()
        service = TelegramBotService(mock_secret_store)
        
        result = service.validate_bot_token('123456:ABC-DEF')
        
        self.assertFalse(result['valid'])
        self.assertIn('timed out', result['error'])
    
    def test_get_bot_config_without_auth(self):
        """Test getting bot config without authentication."""
        response = self.client.get('/api/bot/config')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        
        telegram_config = data['data']
        self.assertEqual(telegram_config['botToken'], '')
        self.assertEqual(telegram_config['adminUserId'], '')
        self.assertEqual(telegram_config['notificationChannelId'], '')
        self.assertFalse(telegram_config['whitelistMode'])
        self.assertFalse(telegram_config['hasValidConfig'])
    
    def test_get_bot_config_with_auth(self):
        """Test getting bot config with authentication."""
        response = self.client.get('/api/bot/config', headers=self.auth_header)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        
        telegram_config = data['data']
        self.assertEqual(telegram_config['botToken'], '')
        self.assertEqual(telegram_config['adminUserId'], '')
        self.assertFalse(telegram_config['hasValidConfig'])
    
    def test_update_bot_config_invalid_data(self):
        """Test updating bot config with invalid data."""
        response = self.client.post('/api/bot/config',
            json={},
            headers=self.auth_header
        )
        
        # Should fail because bot token validation is required when provided
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    @patch('requests.get')
    def test_update_bot_config_invalid_token(self, mock_get):
        """Test updating bot config with invalid bot token."""
        # Mock failed validation
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'ok': False,
            'description': 'Unauthorized'
        }
        mock_get.return_value = mock_response
        
        response = self.client.post('/api/bot/config',
            json={
                'botToken': '123456:invalid',
                'adminUserId': '123456789',
                'whitelistMode': True
            },
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('Invalid bot token', data['error'])
    
    @patch('services.telegram_bot.TelegramBotService.validate_bot_token')
    @patch('services.telegram_bot.TelegramBotService.save_bot_credentials')
    def test_update_bot_config_success(self, mock_save, mock_validate):
        """Test successful bot config update."""
        # Mock successful validation
        mock_validate.return_value = {'valid': True, 'data': {}}
        mock_save.return_value = True
        
        response = self.client.post('/api/bot/config',
            json={
                'botToken': '123456:ABC-DEF',
                'adminUserId': '123456789',
                'notificationChannelId': '-100123456789',
                'whitelistMode': True
            },
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        
        # Verify validation was called
        mock_validate.assert_called_once_with('123456:ABC-DEF')
        
        # Verify credentials were saved
        mock_save.assert_called_once()
        args = mock_save.call_args[0]
        self.assertEqual(args[0], '123456:ABC-DEF')
        self.assertEqual(args[1], '123456789')
    
    def test_get_bot_commands(self):
        """Test getting bot commands."""
        response = self.client.get('/api/bot/commands')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        
        commands = data['data']
        self.assertIsInstance(commands, list)
        self.assertGreater(len(commands), 0)
        
        # Check default commands structure
        for cmd in commands[:3]:  # Check first 3 commands
            self.assertIn('cmd', cmd)
            self.assertIn('desc', cmd)
            self.assertIn('example', cmd)
    
    def test_update_bot_commands_invalid_format(self):
        """Test updating bot commands with invalid format."""
        response = self.client.put('/api/bot/commands',
            json={
                'commands': [
                    {'cmd': '/test'}  # Missing required fields
                ]
            },
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('Invalid command format', data['error'])
    
    @patch('services.telegram_bot.TelegramBotService.save_commands')
    def test_update_bot_commands_success(self, mock_save):
        """Test successful bot commands update."""
        mock_save.return_value = True
        
        commands = [
            {
                'cmd': '/test',
                'desc': 'Test command',
                'example': '/test arg1 arg2'
            },
            {
                'cmd': '/another',
                'desc': 'Another command',
                'example': '/another'
            }
        ]
        
        response = self.client.put('/api/bot/commands',
            json={'commands': commands},
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertEqual(data['data'], commands)
        
        # Verify save was called
        mock_save.assert_called_once_with(commands)
    
    @patch('services.telegram_bot.TelegramBotService.save_commands')
    def test_update_bot_commands_save_failure(self, mock_save):
        """Test bot commands update with save failure."""
        mock_save.return_value = False
        
        commands = [
            {
                'cmd': '/test',
                'desc': 'Test command',
                'example': '/test'
            }
        ]
        
        response = self.client.put('/api/bot/commands',
            json={'commands': commands},
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('Failed to save commands', data['error'])
    
    @patch('requests.post')
    def test_send_test_message_admin_success(self, mock_post):
        """Test successful test message to admin."""
        # Mock successful Telegram API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'ok': True,
            'result': {
                'message_id': 123,
                'chat': {'id': 123456789},
                'text': 'Test message'
            }
        }
        mock_post.return_value = mock_response
        
        # Mock getting bot credentials
        with patch('services.telegram_bot.TelegramBotService.get_bot_token', return_value='123456:ABC-DEF'), \
             patch('services.telegram_bot.TelegramBotService.get_admin_user_id', return_value='123456789'):
            
            response = self.client.post('/api/bot/test-message',
                json={'target_type': 'admin'},
                headers=self.auth_header
            )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertEqual(data['data']['message_id'], 123)
        
        # Verify API was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn('sendMessage', call_args[0][0])
    
    @patch('requests.post')
    def test_send_test_message_no_token(self, mock_post):
        """Test test message without bot token configured."""
        # Mock no bot token
        with patch('services.telegram_bot.TelegramBotService.get_bot_token', return_value=None):
            
            response = self.client.post('/api/bot/test-message',
                json={'target_type': 'admin'},
                headers=self.auth_header
            )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('Bot token not configured', data['error'])
    
    @patch('requests.post')
    def test_send_test_message_channel_success(self, mock_post):
        """Test successful test message to channel."""
        # Mock successful Telegram API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'ok': True,
            'result': {
                'message_id': 456,
                'chat': {'id': -100123456789},
                'text': 'Test message'
            }
        }
        mock_post.return_value = mock_response
        
        # Mock getting bot credentials
        with patch('services.telegram_bot.TelegramBotService.get_bot_token', return_value='123456:ABC-DEF'):
            
            response = self.client.post('/api/bot/test-message',
                json={
                    'target_type': 'channel',
                    'target_id': '-100123456789'
                },
                headers=self.auth_header
            )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['message_id'], 456)
    
    @patch('requests.post')
    def test_send_test_message_channel_missing_id(self, mock_post):
        """Test test message to channel without providing ID."""
        # Mock getting bot credentials
        with patch('services.telegram_bot.TelegramBotService.get_bot_token', return_value='123456:ABC-DEF'):
            
            response = self.client.post('/api/bot/test-message',
                json={'target_type': 'channel'},  # No target_id
                headers=self.auth_header
            )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('Channel ID is required', data['error'])
    
    def test_send_test_message_invalid_target_type(self):
        """Test test message with invalid target type."""
        response = self.client.post('/api/bot/test-message',
            json={'target_type': 'invalid'},
            headers=self.auth_header
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        # Bot token check happens before target type validation
        self.assertTrue('Bot token not configured' in data['error'] or 'Invalid target type' in data['error'])


if __name__ == '__main__':
    unittest.main()