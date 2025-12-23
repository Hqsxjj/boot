# models/__init__.py
# 导出所有数据库模型

from .database import (
    SecretsBase,
    AppDataBase,
    Base,
    init_secrets_db,
    init_appdata_db,
    init_db,
    init_all_databases,
    get_session_factory,
)

from .secret import Secret

from .app_data import (
    AppConfig,
    AdminCredential,
    TaskHistory,
    Cloud115Token,
)

from .config import (
    ConfigEntry,
    AdminUser,
    Subscription,
    SubscriptionHistory,
    SubscriptionSettings,
    Source,
    CrawledResource,
)

from .offline_task import OfflineTask
from .recognition_keyword import RecognitionKeyword
from .missing_episode import MissingEpisode

__all__ = [
    # Database bases and utilities
    'SecretsBase',
    'AppDataBase',
    'Base',
    'init_secrets_db',
    'init_appdata_db',
    'init_db',
    'init_all_databases',
    'get_session_factory',
    # Secret model
    'Secret',
    # App data models
    'AppConfig',
    'AdminCredential',
    'TaskHistory',
    'Cloud115Token',
    # Config models (new)
    'ConfigEntry',
    'AdminUser',
    'Subscription',
    'SubscriptionHistory',
    'SubscriptionSettings',
    'Source',
    'CrawledResource',
    # Task models
    'OfflineTask',
    'RecognitionKeyword',
    'MissingEpisode',
]
