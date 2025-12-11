import unittest
import json
import yaml
import tempfile
import os
from werkzeug.security import generate_password_hash

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import create_app
from persistence.store import DataStore
from persistence.config_store import ConfigStore


class TestConfigStore(unittest.TestCase):
    """Test YAML-backed config persistence layer."""
    
    def setUp(self):
        """Set up temporary YAML and JSON files."""
        self.temp_yaml = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yml')
        self.temp_yaml.close()
        
        self.temp_json = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_json.close()
        
        self.config_store = ConfigStore(yaml_path=self.temp_yaml.name, json_path=self.temp_json.name)
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_yaml.name):
            os.unlink(self.temp_yaml.name)
        if os.path.exists(self.temp_json.name):
            os.unlink(self.temp_json.name)
    
    def test_yaml_file_created_with_defaults(self):
        """Test that YAML file is created with default config."""
        self.assertTrue(os.path.exists(self.temp_yaml.name))
        
        with open(self.temp_yaml.name, 'r') as f:
            config = yaml.safe_load(f)
        
        self.assertIn('telegram', config)
        self.assertIn('cloud115', config)
        self.assertIn('organize', config)
    
    def test_config_round_trip(self):
        """Test that config can be saved and loaded."""
        config = self.config_store.get_config()
        config['telegram']['botToken'] = 'test-token-123'
        config['cloud115']['cookies'] = 'sensitive-cookie-data'
        config['organize']['ai']['apiKey'] = 'sk-sensitive-key'
        
        self.config_store.update_config(config)
        
        loaded = self.config_store.get_config()
        self.assertEqual(loaded['telegram']['botToken'], 'test-token-123')
        self.assertEqual(loaded['cloud115']['cookies'], 'sensitive-cookie-data')
        self.assertEqual(loaded['organize']['ai']['apiKey'], 'sk-sensitive-key')
    
    def test_sensitive_fields_not_masked(self):
        """Test that sensitive fields are stored without masking."""
        config = self.config_store.get_config()
        config['telegram']['botToken'] = 'sensitive-bot-token'
        config['cloud123']['clientSecret'] = 'sensitive-client-secret'
        config['emby']['apiKey'] = 'sensitive-emby-key'
        config['tmdb']['apiKey'] = 'sensitive-tmdb-key'
        config['openList']['password'] = 'sensitive-password'
        config['proxy']['password'] = 'proxy-password'
        config['strm']['webdav']['password'] = 'webdav-password'
        config['organize']['ai']['apiKey'] = 'ai-api-key'
        
        self.config_store.update_config(config)
        
        loaded = self.config_store.get_config()
        # Verify no masking - exact values preserved
        self.assertEqual(loaded['telegram']['botToken'], 'sensitive-bot-token')
        self.assertEqual(loaded['cloud123']['clientSecret'], 'sensitive-client-secret')
        self.assertEqual(loaded['emby']['apiKey'], 'sensitive-emby-key')
        self.assertEqual(loaded['tmdb']['apiKey'], 'sensitive-tmdb-key')
        self.assertEqual(loaded['openList']['password'], 'sensitive-password')
        self.assertEqual(loaded['proxy']['password'], 'proxy-password')
        self.assertEqual(loaded['strm']['webdav']['password'], 'webdav-password')
        self.assertEqual(loaded['organize']['ai']['apiKey'], 'ai-api-key')
        
        # Also verify in YAML file directly
        with open(self.temp_yaml.name, 'r') as f:
            yaml_content = yaml.safe_load(f)
        
        self.assertEqual(yaml_content['telegram']['botToken'], 'sensitive-bot-token')
        self.assertNotIn('*', yaml_content['telegram']['botToken'])
    
    def test_complex_nested_config(self):
        """Test that complex nested structures like movieRules and tvRules work."""
        config = self.config_store.get_config()
        
        config['organize']['movieRules'] = [
            {'id': 'm_anim', 'name': '动画电影', 'targetCid': '123', 'conditions': {'genre_ids': '16'}},
            {'id': 'm_cn', 'name': '华语电影', 'targetCid': '456', 'conditions': {'origin_country': 'CN,TW,HK'}}
        ]
        
        config['organize']['tvRules'] = [
            {'id': 't_cn', 'name': '华语剧集', 'targetCid': '789', 'conditions': {'origin_country': 'CN,TW,HK'}}
        ]
        
        self.config_store.update_config(config)
        
        loaded = self.config_store.get_config()
        self.assertEqual(len(loaded['organize']['movieRules']), 2)
        self.assertEqual(loaded['organize']['movieRules'][0]['name'], '动画电影')
        self.assertEqual(loaded['organize']['movieRules'][1]['targetCid'], '456')
        self.assertEqual(len(loaded['organize']['tvRules']), 1)
        self.assertEqual(loaded['organize']['tvRules'][0]['name'], '华语剧集')
    
    def test_migration_from_json(self):
        """Test migration from existing appdata.json."""
        # Create a JSON file with config
        json_data = {
            'admin': {
                'username': 'admin',
                'password_hash': 'test-hash'
            },
            'config': {
                'telegram': {
                    'botToken': 'json-token',
                    'adminUserId': '12345'
                },
                'cloud115': {
                    'cookies': 'json-cookies',
                    'downloadPath': '999'
                }
            }
        }
        
        with open(self.temp_json.name, 'w') as f:
            json.dump(json_data, f)
        
        # Delete YAML to trigger migration
        if os.path.exists(self.temp_yaml.name):
            os.unlink(self.temp_yaml.name)
        
        # Create new ConfigStore - should trigger migration
        new_store = ConfigStore(yaml_path=self.temp_yaml.name, json_path=self.temp_json.name)
        
        # Verify migration
        config = new_store.get_config()
        self.assertEqual(config['telegram']['botToken'], 'json-token')
        self.assertEqual(config['telegram']['adminUserId'], '12345')
        self.assertEqual(config['cloud115']['cookies'], 'json-cookies')
        self.assertEqual(config['cloud115']['downloadPath'], '999')


class TestDataStoreWithConfigStore(unittest.TestCase):
    """Test DataStore integration with ConfigStore."""
    
    def setUp(self):
        """Set up temporary files."""
        self.temp_yaml = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yml')
        self.temp_yaml.close()
        
        self.temp_json = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_json.close()
        
        self.store = DataStore(data_path=self.temp_json.name, config_yaml_path=self.temp_yaml.name)
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_yaml.name):
            os.unlink(self.temp_yaml.name)
        if os.path.exists(self.temp_json.name):
            os.unlink(self.temp_json.name)
    
    def test_get_config_uses_yaml(self):
        """Test that get_config retrieves from YAML."""
        config = self.store.get_config()
        config['telegram']['botToken'] = 'yaml-token'
        
        self.store.update_config(config)
        
        # Verify in YAML
        with open(self.temp_yaml.name, 'r') as f:
            yaml_data = yaml.safe_load(f)
        
        self.assertEqual(yaml_data['telegram']['botToken'], 'yaml-token')
    
    def test_two_factor_secret_in_json_not_yaml(self):
        """Test that 2FA secret stays in JSON, not YAML."""
        self.store.update_two_factor_secret('test-secret-123')
        
        # Check JSON has it
        with open(self.temp_json.name, 'r') as f:
            json_data = json.load(f)
        
        self.assertEqual(json_data['admin']['two_factor_secret'], 'test-secret-123')
        
        # Check YAML does not have it
        with open(self.temp_yaml.name, 'r') as f:
            yaml_data = yaml.safe_load(f)
        
        self.assertNotIn('twoFactorSecret', yaml_data)
    
    def test_config_includes_2fa_when_enabled(self):
        """Test that get_config includes 2FA secret when enabled."""
        secret = 'JBSWY3DPEHPK3PXP'
        self.store.update_two_factor_secret(secret)
        
        config = self.store.get_config()
        self.assertIn('twoFactorSecret', config)
        self.assertEqual(config['twoFactorSecret'], secret)


class TestConfigAPIEndpoints(unittest.TestCase):
    """Test config API endpoints with YAML store."""
    
    def setUp(self):
        """Set up test client and temporary files."""
        self.temp_yaml = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yml')
        self.temp_yaml.close()
        
        self.temp_json = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_json.close()
        
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        
        # Create a temp directory for database
        self.temp_dir = tempfile.mkdtemp()
        
        # Override paths BEFORE creating app
        os.environ['DATA_PATH'] = self.temp_json.name
        os.environ['CONFIG_YAML_PATH'] = self.temp_yaml.name
        os.environ['DATA_DIR'] = self.temp_dir
        os.environ['DATABASE_URL'] = f'sqlite:///{self.temp_db.name}'
        
        self.app = create_app({
            'TESTING': True,
            'JWT_SECRET_KEY': 'test-secret',
            'SECRET_KEY': 'test-secret'
        })
        
        self.client = self.app.test_client()
        self.store = DataStore(self.temp_json.name, self.temp_yaml.name)
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        if os.path.exists(self.temp_yaml.name):
            os.unlink(self.temp_yaml.name)
        if os.path.exists(self.temp_json.name):
            os.unlink(self.temp_json.name)
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _get_token(self):
        """Helper to get auth token."""
        self.store.update_admin_password(generate_password_hash('testpass'))
        response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'testpass'},
            content_type='application/json'
        )
        return json.loads(response.data)['data']['token']
    
    def test_get_config_returns_unmasked_data(self):
        """Test that GET /api/config returns full unmasked config."""
        token = self._get_token()
        
        # Set some sensitive data
        config = self.store.get_config()
        config['telegram']['botToken'] = 'sensitive-token-12345'
        config['cloud115']['cookies'] = 'sensitive-cookies-data'
        self.store.update_config(config)
        
        # Get config via API
        response = self.client.get('/api/config',
            headers={'Authorization': f'Bearer {token}'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['telegram']['botToken'], 'sensitive-token-12345')
        self.assertEqual(data['data']['cloud115']['cookies'], 'sensitive-cookies-data')
        # No masking - actual values returned
        self.assertNotIn('*', data['data']['telegram']['botToken'])
    
    def test_put_config_works(self):
        """Test that PUT /api/config works."""
        token = self._get_token()
        
        config = self.store.get_config()
        config['telegram']['botToken'] = 'new-token-via-put'
        config['cloud115']['downloadPath'] = '12345'
        
        response = self.client.put('/api/config',
            json=config,
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['telegram']['botToken'], 'new-token-via-put')
        self.assertEqual(data['data']['cloud115']['downloadPath'], '12345')
    
    def test_post_config_works(self):
        """Test that POST /api/config works (for frontend compatibility)."""
        token = self._get_token()
        
        config = self.store.get_config()
        config['telegram']['adminUserId'] = '999888777'
        config['organize']['enabled'] = True
        
        response = self.client.post('/api/config',
            json=config,
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['telegram']['adminUserId'], '999888777')
        self.assertTrue(data['data']['organize']['enabled'])
    
    def test_config_response_shape(self):
        """Test that config responses have correct shape: {success: true, data: <config>}."""
        token = self._get_token()
        
        # Test GET
        response = self.client.get('/api/config',
            headers={'Authorization': f'Bearer {token}'}
        )
        data = json.loads(response.data)
        
        self.assertIn('success', data)
        self.assertIn('data', data)
        self.assertTrue(data['success'])
        self.assertIsInstance(data['data'], dict)
        
        # Test PUT
        config = self.store.get_config()
        response = self.client.put('/api/config',
            json=config,
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertIn('success', data)
        self.assertIn('data', data)
        self.assertTrue(data['success'])
        self.assertIsInstance(data['data'], dict)
        
        # Test POST
        response = self.client.post('/api/config',
            json=config,
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertIn('success', data)
        self.assertIn('data', data)
        self.assertTrue(data['success'])
        self.assertIsInstance(data['data'], dict)
    
    def test_config_keys_match_frontend_schema(self):
        """Test that config keys match frontend AppConfig schema."""
        token = self._get_token()
        
        response = self.client.get('/api/config',
            headers={'Authorization': f'Bearer {token}'}
        )
        data = json.loads(response.data)
        config = data['data']
        
        # Check top-level keys
        expected_keys = ['telegram', 'cloud115', 'cloud123', 'openList', 'proxy', 
                        'tmdb', 'emby', 'strm', 'organize']
        for key in expected_keys:
            self.assertIn(key, config)
        
        # Check nested keys
        self.assertIn('downloadPath', config['cloud115'])
        self.assertIn('movieRules', config['organize'])
        self.assertIn('tvRules', config['organize'])
        self.assertIn('ai', config['organize'])
        self.assertIn('webdav', config['strm'])
        self.assertIn('notifications', config['emby'])
        self.assertIn('missingEpisodes', config['emby'])
    
    def test_dev_mode_allows_unauthenticated(self):
        """Test that ALLOW_UNAUTHENTICATED_CONFIG flag works."""
        # Enable dev mode
        os.environ['ALLOW_UNAUTHENTICATED_CONFIG'] = 'true'
        
        # Try to get config without token
        response = self.client.get('/api/config')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # Cleanup
        os.environ['ALLOW_UNAUTHENTICATED_CONFIG'] = 'false'
    
    def test_sensitive_fields_round_trip(self):
        """Test that all sensitive fields survive round-trip without masking."""
        token = self._get_token()
        
        config = self.store.get_config()
        sensitive_values = {
            'telegram.botToken': '1234567890:ABCdefGHIjklMNOpqrsTUVwxyz',
            'cloud115.cookies': 'UID=123456_A1B2C3D4; CID=ABCD1234; SEID=xyz789',
            'cloud123.clientSecret': 'secret_key_123456789',
            'emby.apiKey': 'abcdef123456789',
            'tmdb.apiKey': 'tmdb_api_key_xyz',
            'openList.password': 'openlist_pass',
            'proxy.password': 'proxy_pass',
            'strm.webdav.password': 'webdav_pass',
            'organize.ai.apiKey': 'sk-openai-key'
        }
        
        # Set values
        config['telegram']['botToken'] = sensitive_values['telegram.botToken']
        config['cloud115']['cookies'] = sensitive_values['cloud115.cookies']
        config['cloud123']['clientSecret'] = sensitive_values['cloud123.clientSecret']
        config['emby']['apiKey'] = sensitive_values['emby.apiKey']
        config['tmdb']['apiKey'] = sensitive_values['tmdb.apiKey']
        config['openList']['password'] = sensitive_values['openList.password']
        config['proxy']['password'] = sensitive_values['proxy.password']
        config['strm']['webdav']['password'] = sensitive_values['strm.webdav.password']
        config['organize']['ai']['apiKey'] = sensitive_values['organize.ai.apiKey']
        
        # Save via API
        response = self.client.post('/api/config',
            json=config,
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Get via API
        response = self.client.get('/api/config',
            headers={'Authorization': f'Bearer {token}'}
        )
        
        data = json.loads(response.data)
        retrieved_config = data['data']
        
        # Verify all values match exactly (no masking)
        self.assertEqual(retrieved_config['telegram']['botToken'], sensitive_values['telegram.botToken'])
        self.assertEqual(retrieved_config['cloud115']['cookies'], sensitive_values['cloud115.cookies'])
        self.assertEqual(retrieved_config['cloud123']['clientSecret'], sensitive_values['cloud123.clientSecret'])
        self.assertEqual(retrieved_config['emby']['apiKey'], sensitive_values['emby.apiKey'])
        self.assertEqual(retrieved_config['tmdb']['apiKey'], sensitive_values['tmdb.apiKey'])
        self.assertEqual(retrieved_config['openList']['password'], sensitive_values['openList.password'])
        self.assertEqual(retrieved_config['proxy']['password'], sensitive_values['proxy.password'])
        self.assertEqual(retrieved_config['strm']['webdav']['password'], sensitive_values['strm.webdav.password'])
        self.assertEqual(retrieved_config['organize']['ai']['apiKey'], sensitive_values['organize.ai.apiKey'])


if __name__ == '__main__':
    unittest.main()
