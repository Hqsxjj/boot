import json
import os
from typing import Dict, Any, Optional
from threading import Lock
from .config_store import ConfigStore


class DataStore:
    """Persistence layer for admin credentials and 2FA secrets. Config is managed by ConfigStore."""
    
    def __init__(self, data_path: str = None, config_yaml_path: str = None):
        self.data_path = data_path or os.environ.get('DATA_PATH', '/data/appdata.json')
        self._lock = Lock()
        self._ensure_data_dir()
        self._ensure_data_file()
        
        # Initialize YAML-backed config store
        self.config_store = ConfigStore(yaml_path=config_yaml_path, json_path=self.data_path)
    
    def _ensure_data_dir(self):
        """Create data directory if it doesn't exist."""
        data_dir = os.path.dirname(self.data_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
    
    def _ensure_data_file(self):
        """Create data file with default structure if it doesn't exist."""
        if not os.path.exists(self.data_path):
            default_data = {
                'admin': {
                    'username': 'admin',
                    'password_hash': None,
                    'two_factor_secret': None,
                    'two_factor_enabled': False
                },
                'config': self._get_default_config()
            }
            self._write_data(default_data)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default AppConfig structure."""
        return {
            'telegram': {
                'botToken': '',
                'adminUserId': '',
                'whitelistMode': False,
                'notificationChannelId': ''
            },
            'cloud115': {
                'loginMethod': 'cookie',
                'loginApp': 'web',
                'cookies': '',
                'userAgent': '',
                'downloadPath': '',
                'downloadDirName': '',
                'autoDeleteMsg': False,
                'qps': 1
            },
            'cloud123': {
                'enabled': False,
                'clientId': '',
                'clientSecret': '',
                'downloadPath': '',
                'downloadDirName': '',
                'qps': 1
            },
            'openList': {
                'enabled': False,
                'url': '',
                'mountPath': '',
                'username': '',
                'password': ''
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
                'language': 'en-US',
                'includeAdult': False
            },
            'emby': {
                'enabled': False,
                'serverUrl': '',
                'apiKey': '',
                'refreshAfterOrganize': False,
                'notifications': {
                    'enabled': False,
                    'forwardToTelegram': False,
                    'includePosters': False,
                    'playbackReportingFreq': 'daily'
                },
                'missingEpisodes': {
                    'enabled': False,
                    'cronSchedule': '0 0 * * *'
                }
            },
            'strm': {
                'enabled': False,
                'outputDir': '',
                'sourceCid115': '',
                'urlPrefix115': '',
                'sourceDir123': '',
                'urlPrefix123': '',
                'sourcePathOpenList': '',
                'urlPrefixOpenList': '',
                'webdav': {
                    'enabled': False,
                    'port': '8080',
                    'username': '',
                    'password': '',
                    'readOnly': True
                }
            },
            'organize': {
                'enabled': False,
                'sourceCid': '',
                'sourceDirName': '',
                'targetCid': '',
                'targetDirName': '',
                'ai': {
                    'enabled': False,
                    'provider': 'openai',
                    'baseUrl': '',
                    'apiKey': '',
                    'model': ''
                },
                'rename': {
                    'enabled': False,
                    'movieTemplate': '',
                    'seriesTemplate': '',
                    'addTmdbIdToFolder': False
                },
                'movieRules': [],
                'tvRules': []
            }
        }
    
    def _read_data(self) -> Dict[str, Any]:
        """Read data from file with thread safety."""
        with self._lock:
            try:
                with open(self.data_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {
                    'admin': {
                        'username': 'admin',
                        'password_hash': None,
                        'two_factor_secret': None,
                        'two_factor_enabled': False
                    },
                    'config': self._get_default_config()
                }
    
    def _write_data(self, data: Dict[str, Any]):
        """Write data to file with thread safety."""
        with self._lock:
            with open(self.data_path, 'w') as f:
                json.dump(data, f, indent=2)
    
    def get_admin_credentials(self) -> Dict[str, Any]:
        """Get admin credentials."""
        data = self._read_data()
        return data.get('admin', {
            'username': 'admin',
            'password_hash': None,
            'two_factor_secret': None,
            'two_factor_enabled': False
        })
    
    def update_admin_password(self, password_hash: str):
        """Update admin password hash."""
        data = self._read_data()
        if 'admin' not in data:
            data['admin'] = {'username': 'admin'}
        data['admin']['password_hash'] = password_hash
        self._write_data(data)
    
    def get_two_factor_secret(self) -> Optional[str]:
        """Get 2FA secret."""
        data = self._read_data()
        return data.get('admin', {}).get('two_factor_secret')
    
    def update_two_factor_secret(self, secret: str):
        """Update 2FA secret."""
        data = self._read_data()
        if 'admin' not in data:
            data['admin'] = {'username': 'admin'}
        data['admin']['two_factor_secret'] = secret
        data['admin']['two_factor_enabled'] = True
        self._write_data(data)
    
    def is_two_factor_enabled(self) -> bool:
        """Check if 2FA is enabled."""
        data = self._read_data()
        return data.get('admin', {}).get('two_factor_enabled', False)
    
    def get_config(self) -> Dict[str, Any]:
        """Get full app config from YAML store."""
        config = self.config_store.get_config()
        
        # Add 2FA secret to config if enabled
        if self.is_two_factor_enabled():
            config['twoFactorSecret'] = self.get_two_factor_secret()
        
        return config
    
    def update_config(self, config: Dict[str, Any]):
        """Update app config in YAML store."""
        # Extract 2FA secret if present and update separately in JSON
        config_copy = config.copy()
        if 'twoFactorSecret' in config_copy:
            two_factor_secret = config_copy.pop('twoFactorSecret')
            if two_factor_secret:
                self.update_two_factor_secret(two_factor_secret)
        
        # Update config in YAML store
        self.config_store.update_config(config_copy)
