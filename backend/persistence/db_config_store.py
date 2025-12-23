# persistence/db_config_store.py
# 数据库配置存储 - 替代 YAML/JSON 文件存储

import json
import logging
from typing import Dict, Any, Optional
from threading import Lock
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DbConfigStore:
    """
    数据库配置存储服务
    替代原来的 ConfigStore (YAML) 和 DataStore (JSON)
    """
    
    def __init__(self, session_factory):
        """
        初始化数据库配置存储
        
        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory
        self._lock = Lock()
        self._cache = None  # 配置缓存
        self._cache_dirty = True
        logger.info('DbConfigStore initialized')
    
    def _get_session(self) -> Session:
        """获取数据库 session"""
        return self.session_factory()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """返回默认配置结构"""
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
    
    def get_config(self) -> Dict[str, Any]:
        """
        获取完整配置
        从数据库读取并合并默认值
        """
        # 使用缓存
        if self._cache is not None and not self._cache_dirty:
            return self._cache.copy()
        
        with self._lock:
            session = self._get_session()
            try:
                from models.config import ConfigEntry
                
                # 读取所有配置条目
                entries = session.query(ConfigEntry).all()
                
                # 从默认配置开始
                config = self._get_default_config()
                
                # 应用数据库中的配置
                for entry in entries:
                    self._set_nested_value(config, entry.key, entry.get_value())
                
                self._cache = config
                self._cache_dirty = False
                
                return config.copy()
            except Exception as e:
                logger.error(f'Failed to get config: {e}')
                return self._get_default_config()
            finally:
                session.close()
    
    def update_config(self, config: Dict[str, Any]):
        """
        更新配置
        将嵌套配置扁平化存储到数据库
        """
        with self._lock:
            session = self._get_session()
            try:
                from models.config import ConfigEntry
                
                # 扁平化配置
                flat_config = self._flatten_dict(config)
                
                for key, value in flat_config.items():
                    # 跳过 twoFactorSecret，它存储在其他地方
                    if key == 'twoFactorSecret':
                        continue
                    
                    # 确定 category
                    category = key.split('.')[0] if '.' in key else 'general'
                    
                    # 查找或创建条目
                    entry = session.query(ConfigEntry).filter(ConfigEntry.key == key).first()
                    if entry:
                        entry.set_value(value)
                    else:
                        entry = ConfigEntry(key=key, category=category)
                        entry.set_value(value)
                        session.add(entry)
                
                session.commit()
                self._cache_dirty = True
                logger.debug(f'Config updated: {len(flat_config)} entries')
            except Exception as e:
                session.rollback()
                logger.error(f'Failed to update config: {e}')
                raise
            finally:
                session.close()
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """获取单个配置值"""
        config = self.get_config()
        return self._get_nested_value(config, key, default)
    
    def set_value(self, key: str, value: Any, category: str = 'general'):
        """设置单个配置值"""
        with self._lock:
            session = self._get_session()
            try:
                from models.config import ConfigEntry
                
                entry = session.query(ConfigEntry).filter(ConfigEntry.key == key).first()
                if entry:
                    entry.set_value(value)
                else:
                    entry = ConfigEntry(key=key, category=category)
                    entry.set_value(value)
                    session.add(entry)
                
                session.commit()
                self._cache_dirty = True
            except Exception as e:
                session.rollback()
                logger.error(f'Failed to set value {key}: {e}')
                raise
            finally:
                session.close()
    
    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
        """将嵌套字典扁平化为 key.subkey 形式"""
        items = []
        for k, v in d.items():
            new_key = f'{parent_key}{sep}{k}' if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    def _set_nested_value(self, d: Dict, key: str, value: Any, sep: str = '.'):
        """根据扁平化的 key 设置嵌套值"""
        keys = key.split(sep)
        current = d
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
    
    def _get_nested_value(self, d: Dict, key: str, default: Any = None, sep: str = '.') -> Any:
        """根据扁平化的 key 获取嵌套值"""
        keys = key.split(sep)
        current = d
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        return current
    
    def invalidate_cache(self):
        """使缓存失效"""
        self._cache_dirty = True
    
    # ========== 管理员凭证方法 ==========
    
    def get_admin_user(self) -> Dict[str, Any]:
        """获取管理员用户信息"""
        session = self._get_session()
        try:
            from models.config import AdminUser
            
            admin = session.query(AdminUser).filter(AdminUser.username == 'admin').first()
            if admin:
                return {
                    'username': admin.username,
                    'two_factor_enabled': admin.two_factor_enabled
                }
            
            # 创建默认管理员
            admin = AdminUser(username='admin', two_factor_enabled=False)
            session.add(admin)
            session.commit()
            
            return {
                'username': 'admin',
                'two_factor_enabled': False
            }
        except Exception as e:
            logger.error(f'Failed to get admin user: {e}')
            return {'username': 'admin', 'two_factor_enabled': False}
        finally:
            session.close()
    
    def update_two_factor(self, enabled: bool):
        """更新 2FA 状态"""
        session = self._get_session()
        try:
            from models.config import AdminUser
            
            admin = session.query(AdminUser).filter(AdminUser.username == 'admin').first()
            if admin:
                admin.two_factor_enabled = enabled
            else:
                admin = AdminUser(username='admin', two_factor_enabled=enabled)
                session.add(admin)
            
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to update 2FA: {e}')
            raise
        finally:
            session.close()
    
    def is_two_factor_enabled(self) -> bool:
        """检查 2FA 是否启用"""
        admin = self.get_admin_user()
        return admin.get('two_factor_enabled', False)


# 全局实例
_db_config_store: Optional[DbConfigStore] = None


def get_db_config_store() -> Optional[DbConfigStore]:
    """获取全局数据库配置存储实例"""
    return _db_config_store


def init_db_config_store(session_factory) -> DbConfigStore:
    """初始化全局数据库配置存储"""
    global _db_config_store
    _db_config_store = DbConfigStore(session_factory)
    return _db_config_store
