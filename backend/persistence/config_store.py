import os
import json
import yaml
from typing import Dict, Any
from threading import Lock


class ConfigStore:
    """YAML-based persistence layer for app configuration."""
    
    def __init__(self, yaml_path: str = None, json_path: str = None):
        """
        Initialize the config store.
        
        Args:
            yaml_path: Path to YAML config file (default: /data/config.yml)
            json_path: Path to legacy JSON file for migration (default: /data/appdata.json)
        """
        self.yaml_path = yaml_path or os.environ.get('CONFIG_YAML_PATH', '/data/config.yml')
        self.json_path = json_path or os.environ.get('DATA_PATH', '/data/appdata.json')
        self._lock = Lock()
        self._ensure_data_dir()
        self._migrate_from_json_if_needed()
        self._ensure_yaml_file()
    
    def _ensure_data_dir(self):
        """Create data directory if it doesn't exist."""
        yaml_dir = os.path.dirname(self.yaml_path)
        if yaml_dir and not os.path.exists(yaml_dir):
            try:
                os.makedirs(yaml_dir, exist_ok=True)
            except PermissionError:
                # If we can't create the directory (e.g., /data in tests),
                # use a temp directory instead
                import tempfile
                temp_dir = tempfile.gettempdir()
                yaml_filename = os.path.basename(self.yaml_path)
                self.yaml_path = os.path.join(temp_dir, yaml_filename)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default AppConfig structure matching frontend schema."""
        return {
            'telegram': {
                'botToken': '',
                'adminUserId': '',
                'whitelistMode': True,
                'notificationChannelId': ''
            },
            'cloud115': {
                'loginMethod': 'cookie',
                'loginApp': 'web',
                'cookies': '',
                'appId': '',
                'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'downloadPath': '0',
                'downloadDirName': '根目录',
                'autoDeleteMsg': True,
                'qps': 0.8
            },
            'cloud123': {
                'enabled': False,
                'clientId': '',
                'clientSecret': '',
                'downloadPath': '0',
                'downloadDirName': '根目录',
                'qps': 1.0
            },
            'openList': {
                'enabled': False,
                'url': 'http://localhost:5244',
                'mountPath': '/d',
                'username': '',
                'password': ''
            },
            'proxy': {
                'enabled': False,
                'type': 'http',
                'host': '127.0.0.1',
                'port': '7890'
            },
            'tmdb': {
                'apiKey': '',
                'language': 'zh-CN',
                'includeAdult': False
            },
            'emby': {
                'enabled': False,
                'serverUrl': 'http://localhost:8096',
                'apiKey': '',
                'refreshAfterOrganize': True,
                'notifications': {
                    'enabled': True,
                    'forwardToTelegram': True,
                    'includePosters': True,
                    'playbackReportingFreq': 'weekly'
                },
                'missingEpisodes': {
                    'enabled': False,
                    'cronSchedule': '0 0 * * *'
                }
            },
            'strm': {
                'enabled': False,
                'outputDir': '/strm/bot',
                'sourceCid115': '0',
                'urlPrefix115': 'http://127.0.0.1:9527/d/115',
                'sourceDir123': '/',
                'urlPrefix123': 'http://127.0.0.1:9527/d/123',
                'sourcePathOpenList': '/',
                'urlPrefixOpenList': 'http://127.0.0.1:5244/d',
                'webdav': {
                    'enabled': False,
                    'port': '5005',
                    'username': 'admin',
                    'password': 'password',
                    'readOnly': True
                }
            },
            'organize': {
                'enabled': False,
                'sourceCid': '0',
                'sourceDirName': '根目录',
                'targetCid': '0',
                'targetDirName': '根目录',
                'ai': {
                    'enabled': False,
                    'provider': 'openai',
                    'baseUrl': 'https://api.openai.com/v1',
                    'apiKey': '',
                    'model': 'gpt-3.5-turbo'
                },
                'rename': {
                    'enabled': True,
                    'movieTemplate': '{{title}}{% if year %} ({{year}}){% endif %}{% if part %}-{{part}}{% endif %}{% if tmdbid %} {tmdb-{{tmdbid}}}{% endif %}{% if resolution %} [{{resolution}}]{% endif %}{% if version %} [{{version}}]{% endif %}',
                    'seriesTemplate': '{{title}} - {{season_episode}}{% if part %}-{{part}}{% endif %}{% if episode %} - 第 {{episode}} 集{% endif %}{% if tmdbid %} {tmdb-{{tmdbid}}}{% endif %}{% if resolution %} [{{resolution}}]{% endif %}{% if version %} [{{version}}]{% endif %}',
                    'movieDirTemplate': '{% if year %}{{year}}{% else %}未知{% endif %}/{{title}}{% if year %} ({{year}}){% endif %}{% if tmdbid %} {tmdb-{{tmdbid}}}{% endif %}',
                    'seriesDirTemplate': '{% if year %}{{year}}{% else %}未知{% endif %}/{{title}}{% if year %} ({{year}}){% endif %}{% if tmdbid %} {tmdb-{{tmdbid}}}{% endif %}/Season {{season}}',
                    'addTmdbIdToFolder': True
                },
                'movieRules': [],
                'tvRules': []
            }
        }
    
    def _migrate_from_json_if_needed(self):
        """Migrate existing config from appdata.json to config.yml if needed."""
        # Only migrate if YAML doesn't exist but JSON does
        if os.path.exists(self.yaml_path) or not os.path.exists(self.json_path):
            return
        
        try:
            with open(self.json_path, 'r') as f:
                json_data = json.load(f)
            
            # Extract config section from JSON
            if 'config' in json_data:
                config = json_data['config']
                # Write to YAML
                with self._lock:
                    with open(self.yaml_path, 'w') as f:
                        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
                print(f"Migrated config from {self.json_path} to {self.yaml_path}")
        except Exception as e:
            print(f"Warning: Failed to migrate config from JSON: {e}")
    
    def _ensure_yaml_file(self):
        """Create YAML file with default structure if it doesn't exist or is empty."""
        if not os.path.exists(self.yaml_path) or os.path.getsize(self.yaml_path) == 0:
            default_config = self._get_default_config()
            self._write_yaml(default_config)
    
    def _read_yaml(self) -> Dict[str, Any]:
        """Read config from YAML file with thread safety."""
        with self._lock:
            try:
                with open(self.yaml_path, 'r') as f:
                    data = yaml.safe_load(f)
                    return data if data else self._get_default_config()
            except (yaml.YAMLError, FileNotFoundError) as e:
                print(f"Warning: Failed to read YAML config: {e}")
                return self._get_default_config()
    
    def _write_yaml(self, config: Dict[str, Any]):
        """Write config to YAML file with thread safety."""
        with self._lock:
            with open(self.yaml_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    def get_config(self) -> Dict[str, Any]:
        """Get full app config from YAML."""
        config = self._read_yaml()
        # Ensure all default keys exist (for backwards compatibility)
        default = self._get_default_config()
        return self._deep_merge(default, config)
    
    def update_config(self, config: Dict[str, Any]):
        """Update app config in YAML."""
        # Remove twoFactorSecret if present - it's managed separately in JSON
        config_copy = {k: v for k, v in config.items() if k != 'twoFactorSecret'}
        self._write_yaml(config_copy)
    
    def _deep_merge(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
