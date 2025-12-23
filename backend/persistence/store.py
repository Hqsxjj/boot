# persistence/store.py
# 重构后的 DataStore - 使用数据库存储替代文件存储

import logging
from typing import Dict, Any, Optional
from threading import Lock
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

# Default admin password hash for 'password'
DEFAULT_PASSWORD_HASH = generate_password_hash('password')


class DataStore:
    """
    持久化层 - 现在完全使用数据库存储
    管理员凭证、2FA秘钥存储在 SecretStore
    配置存储在 DbConfigStore
    """
    
    def __init__(self, session_factory=None, secret_store=None):
        """
        初始化 DataStore
        
        Args:
            session_factory: SQLAlchemy session factory for appdata.db
            secret_store: SecretStore instance for sensitive data
        """
        self._lock = Lock()
        self.session_factory = session_factory
        self.secret_store = secret_store
        self._db_config_store = None
        
        # 如果有 session_factory，初始化数据库配置存储
        if session_factory:
            from .db_config_store import DbConfigStore
            self._db_config_store = DbConfigStore(session_factory)
        
        logger.info('DataStore initialized with database backend')
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default AppConfig structure."""
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
                'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'downloadPath': '0',
                'downloadDirName': '根目录',
                'autoDeleteMsg': True,
                'qps': 0.8
            },
            'cloud123': {
                'enabled': False,
                'loginMethod': 'oauth',
                'clientId': '',
                'clientSecret': '',
                'passport': '',
                'password': '',
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
                'port': '7890',
                'noProxyHosts': '115.com,123pan.com,123pan.cn'
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
                'enabled': True,  # 默认启用整理工作流
                'sourceCid115': '0',
                'sourceDirName115': '根目录',
                'targetCid115': '0',
                'targetDirName115': '根目录',
                'sourceCid123': '0',
                'sourceDirName123': '根目录',
                'targetCid123': '0',
                'targetDirName123': '根目录',
                'ai': {
                    'enabled': False,
                    'provider': 'openai',
                    'baseUrl': 'https://api.openai.com/v1',
                    'apiKey': '',
                    'model': 'gpt-3.5-turbo'
                },
                'rename': {
                    'enabled': True,
                    'movieTemplate': '{{title}}{% if year %} ({{year}}){% endif %}',
                    'seriesTemplate': '{{title}} - {{season_episode}}',
                    'movieDirTemplate': '{% if year %}{{year}}{% else %}未知{% endif %}/{{title}}',
                    'seriesDirTemplate': '{% if year %}{{year}}{% else %}未知{% endif %}/{{title}}/Season {{season}}',
                    'addTmdbIdToFolder': True
                },
                'movieRules': [],
                'tvRules': []
            }
        }
    
    def get_admin_credentials(self) -> Dict[str, Any]:
        """Get admin credentials from SecretStore."""
        result = {
            'username': 'admin',
            'password_hash': DEFAULT_PASSWORD_HASH,
            'two_factor_secret': None,
            'two_factor_enabled': False
        }
        
        if self.secret_store:
            # 从 SecretStore 获取密码哈希
            password_hash = self.secret_store.get_secret('admin_password_hash')
            if password_hash:
                result['password_hash'] = password_hash
            
            # 获取 2FA 秘钥
            two_factor_secret = self.secret_store.get_secret('admin_2fa_secret')
            if two_factor_secret:
                result['two_factor_secret'] = two_factor_secret
                result['two_factor_enabled'] = True
        
        return result
    
    def update_admin_password(self, password_hash: str):
        """Update admin password hash in SecretStore."""
        if self.secret_store:
            self.secret_store.set_secret('admin_password_hash', password_hash)
            logger.info('Admin password updated')
        else:
            logger.warning('SecretStore not available, password not saved')
    
    def get_two_factor_secret(self) -> Optional[str]:
        """Get 2FA secret from SecretStore."""
        if self.secret_store:
            return self.secret_store.get_secret('admin_2fa_secret')
        return None
    
    def update_two_factor_secret(self, secret: str):
        """Update 2FA secret in SecretStore."""
        if self.secret_store:
            self.secret_store.set_secret('admin_2fa_secret', secret)
            logger.info('2FA secret updated')
    
    def is_two_factor_enabled(self) -> bool:
        """Check if 2FA is enabled."""
        secret = self.get_two_factor_secret()
        return bool(secret)
    
    def disable_two_factor(self):
        """Disable 2FA by removing the secret."""
        if self.secret_store:
            self.secret_store.delete_secret('admin_2fa_secret')
            logger.info('2FA disabled')
    
    def get_config(self) -> Dict[str, Any]:
        """Get full app config from database."""
        if self._db_config_store:
            config = self._db_config_store.get_config()
        else:
            config = self._get_default_config()
        
        # Add 2FA secret to config if enabled
        if self.is_two_factor_enabled():
            config['twoFactorSecret'] = self.get_two_factor_secret()
        
        return config
    
    def update_config(self, config: Dict[str, Any]):
        """Update app config in database."""
        # Extract 2FA secret if present and update separately
        config_copy = config.copy()
        if 'twoFactorSecret' in config_copy:
            two_factor_secret = config_copy.pop('twoFactorSecret')
            if two_factor_secret:
                self.update_two_factor_secret(two_factor_secret)
        
        # Update config in database
        if self._db_config_store:
            self._db_config_store.update_config(config_copy)
        else:
            logger.warning('DbConfigStore not available, config not saved')
    
    def invalidate_cache(self):
        """Invalidate config cache."""
        if self._db_config_store:
            self._db_config_store.invalidate_cache()
