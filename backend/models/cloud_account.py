"""
Cloud Account model for multi-account management.
Reference: EmbyNginxDK Cookie115 model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from models.database import AppDataBase


class CloudAccount(AppDataBase):
    """Model for storing multiple cloud accounts (115, 123, etc.)"""
    __tablename__ = 'cloud_accounts'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)  # 用户自定义名称
    account_type = Column(String(20), nullable=False)  # 115, 115open, 123, 123open
    
    # Cookie 相关
    cookie = Column(Text, nullable=True)  # Cookie 字符串
    client = Column(String(50), nullable=True)  # 客户端类型: android, ios, tv 等
    
    # 115 Open API 专用字段
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    expires_in = Column(Integer, nullable=True)
    refresh_time = Column(Integer, nullable=True)
    app_id = Column(String(50), nullable=True)  # 第三方 App ID
    
    # 123 云盘专用字段
    client_id = Column(String(100), nullable=True)
    client_secret = Column(String(200), nullable=True)
    passport = Column(String(100), nullable=True)  # 手机号/邮箱
    password = Column(String(200), nullable=True)
    
    # 通用字段
    is_active = Column(Boolean, default=False)  # 是否为当前激活账号
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convert to dictionary (hide sensitive data by default)."""
        return {
            'id': self.id,
            'name': self.name,
            'account_type': self.account_type,
            'client': self.client,
            'app_id': self.app_id,
            'is_active': self.is_active,
            'has_cookie': bool(self.cookie),
            'has_token': bool(self.access_token),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_full_dict(self):
        """Convert to full dictionary (including sensitive data for internal use)."""
        return {
            'id': self.id,
            'name': self.name,
            'account_type': self.account_type,
            'cookie': self.cookie,
            'client': self.client,
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'expires_in': self.expires_in,
            'refresh_time': self.refresh_time,
            'app_id': self.app_id,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'passport': self.passport,
            'password': self.password,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
