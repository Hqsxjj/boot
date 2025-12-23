# models/config.py
# 应用配置数据库模型 - 替代 YAML/JSON 文件存储

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Boolean, Integer
from sqlalchemy.sql import func
from .database import AppDataBase
import json


class ConfigEntry(AppDataBase):
    """
    通用配置存储表 - 键值对形式存储所有配置
    替代原来的 config.yml 和 appdata.json
    """
    __tablename__ = 'config_entries'
    
    key = Column(String(255), primary_key=True, nullable=False)
    value = Column(Text, nullable=True)  # JSON 格式存储复杂值
    category = Column(String(100), default='general', index=True)
    value_type = Column(String(50), default='string')  # string, json, bool, int
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def get_value(self):
        """根据 value_type 返回正确类型的值"""
        if self.value is None:
            return None
        if self.value_type == 'json':
            try:
                return json.loads(self.value)
            except:
                return self.value
        elif self.value_type == 'bool':
            return self.value.lower() in ('true', '1', 'yes')
        elif self.value_type == 'int':
            try:
                return int(self.value)
            except:
                return 0
        return self.value
    
    def set_value(self, val):
        """根据值类型设置 value 和 value_type"""
        if val is None:
            self.value = None
            self.value_type = 'string'
        elif isinstance(val, bool):
            self.value = str(val).lower()
            self.value_type = 'bool'
        elif isinstance(val, int):
            self.value = str(val)
            self.value_type = 'int'
        elif isinstance(val, (dict, list)):
            self.value = json.dumps(val, ensure_ascii=False)
            self.value_type = 'json'
        else:
            self.value = str(val)
            self.value_type = 'string'
    
    def __repr__(self):
        return f'<ConfigEntry(key={self.key}, category={self.category})>'


class AdminUser(AppDataBase):
    """
    管理员用户表 - 替代 appdata.json 中的 admin 部分
    密码哈希存储在 SecretStore 中
    """
    __tablename__ = 'admin_users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, default='admin')
    two_factor_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f'<AdminUser(username={self.username}, 2fa={self.two_factor_enabled})>'


class Subscription(AppDataBase):
    """
    订阅表 - 替代 subscriptions.json
    """
    __tablename__ = 'subscriptions'
    
    id = Column(String(36), primary_key=True)  # UUID
    keyword = Column(String(255), nullable=False)
    cloud_type = Column(String(20), default='115')  # 115, 123
    filter_config = Column(Text)  # JSON 格式的过滤配置
    enabled = Column(Boolean, default=True)
    last_check = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'keyword': self.keyword,
            'cloud_type': self.cloud_type,
            'filter_config': json.loads(self.filter_config) if self.filter_config else {},
            'enabled': self.enabled,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    def __repr__(self):
        return f'<Subscription(id={self.id}, keyword={self.keyword})>'


class SubscriptionHistory(AppDataBase):
    """
    订阅历史表 - 替代 subscription_history.json
    """
    __tablename__ = 'subscription_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(String(36), nullable=False, index=True)
    resource_title = Column(String(500))
    resource_url = Column(Text)
    cloud_type = Column(String(20))
    status = Column(String(50), default='found')  # found, saved, failed
    details = Column(Text)  # JSON
    created_at = Column(DateTime, default=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'subscription_id': self.subscription_id,
            'resource_title': self.resource_title,
            'resource_url': self.resource_url,
            'cloud_type': self.cloud_type,
            'status': self.status,
            'details': json.loads(self.details) if self.details else {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SubscriptionSettings(AppDataBase):
    """
    订阅设置表 - 替代 subscription_settings.json
    """
    __tablename__ = 'subscription_settings'
    
    key = Column(String(100), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Source(AppDataBase):
    """
    来源表 - 替代 sources.json
    """
    __tablename__ = 'sources'
    
    id = Column(String(36), primary_key=True)  # UUID
    type = Column(String(50), nullable=False)  # telegram, website
    url = Column(String(500), nullable=False)
    name = Column(String(200))
    enabled = Column(Boolean, default=True)
    last_crawl = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'url': self.url,
            'name': self.name,
            'enabled': self.enabled,
            'last_crawl': self.last_crawl.isoformat() if self.last_crawl else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    def __repr__(self):
        return f'<Source(id={self.id}, type={self.type}, url={self.url})>'


class CrawledResource(AppDataBase):
    """
    抓取的资源表 - 替代 crawled_data.json
    """
    __tablename__ = 'crawled_resources'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(36), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    url = Column(Text)
    share_code = Column(String(100))
    access_code = Column(String(50))
    cloud_type = Column(String(20))  # 115, 123
    file_size = Column(String(50))
    extra_data = Column(Text)  # JSON
    created_at = Column(DateTime, default=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'source_id': self.source_id,
            'title': self.title,
            'url': self.url,
            'share_code': self.share_code,
            'access_code': self.access_code,
            'cloud_type': self.cloud_type,
            'file_size': self.file_size,
            'extra_data': json.loads(self.extra_data) if self.extra_data else {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    def __repr__(self):
        return f'<CrawledResource(id={self.id}, title={self.title})>'
