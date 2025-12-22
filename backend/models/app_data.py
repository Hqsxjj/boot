# models/app_data.py
# 普通应用数据模型 (非敏感数据)

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean
from sqlalchemy.sql import func
from .database import AppDataBase


class AppConfig(AppDataBase):
    """Model for storing non-sensitive application configuration."""
    __tablename__ = 'app_config'
    
    key = Column(String(255), primary_key=True, nullable=False)
    value = Column(Text, nullable=True)
    category = Column(String(100), default='general')  # telegram, cloud, emby, etc.
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f'<AppConfig(key={self.key}, category={self.category})>'


class AdminCredential(AppDataBase):
    """Model for admin authentication (password hash stored encrypted in secrets.db)."""
    __tablename__ = 'admin_credentials'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, default='admin')
    two_factor_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f'<AdminCredential(username={self.username})>'


class TaskHistory(AppDataBase):
    """Model for storing task execution history."""
    __tablename__ = 'task_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(100), nullable=False)  # offline, strm, organize
    status = Column(String(50), default='pending')  # pending, running, completed, failed
    details = Column(Text)  # JSON details
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f'<TaskHistory(id={self.id}, task_type={self.task_type}, status={self.status})>'


class Cloud115Token(AppDataBase):
    """
    Model for storing 115 cloud tokens and cookies.
    Supports both Cookie login and Open Platform OAuth tokens.
    """
    __tablename__ = 'cloud115_tokens'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)  # 账号名称
    token_type = Column(String(50), nullable=False)  # 'cookie' or 'open'
    
    # Cookie 模式字段
    cookie = Column(Text, nullable=True)  # Cookie 字符串
    client = Column(String(50), nullable=True)  # 登录客户端类型 (tv, android, etc.)
    
    # Open Platform 模式字段
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Token 过期时间
    app_id = Column(String(100), nullable=True)  # 第三方 App ID
    
    # 通用字段
    user_id = Column(String(100), nullable=True)  # 115 用户 ID
    user_name = Column(String(100), nullable=True)  # 115 用户名
    is_active = Column(Boolean, default=True)  # 是否为当前激活账号
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'tokenType': self.token_type,
            'client': self.client,
            'userId': self.user_id,
            'userName': self.user_name,
            'isActive': self.is_active,
            'expiresAt': self.expires_at.isoformat() if self.expires_at else None,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f'<Cloud115Token(name={self.name}, type={self.token_type}, active={self.is_active})>'

