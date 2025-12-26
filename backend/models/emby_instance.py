"""
多 Emby 实例管理模型
支持配置和管理多个 Emby 服务器
"""
from sqlalchemy import Column, String, Boolean, DateTime
from datetime import datetime
from .database import AppDataBase


class EmbyInstance(AppDataBase):
    """Emby 实例配置"""
    __tablename__ = 'emby_instances'
    
    id = Column(String, primary_key=True)  # UUID
    name = Column(String, nullable=False)  # 显示名称
    server_url = Column(String, nullable=False)  # 服务器地址
    api_key = Column(String, nullable=False)  # API 密钥
    is_default = Column(Boolean, default=False)  # 是否为默认实例
    is_active = Column(Boolean, default=True)  # 是否启用
    created_at = Column(DateTime, default=datetime.now)
    last_connected = Column(DateTime, nullable=True)  # 最后连接时间
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'serverUrl': self.server_url,
            'apiKey': '***' + self.api_key[-4:] if self.api_key else '',  # 脱敏
            'isDefault': self.is_default,
            'isActive': self.is_active,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'lastConnected': self.last_connected.isoformat() if self.last_connected else None
        }
    
    def to_dict_full(self):
        """完整数据（包含 API Key）"""
        d = self.to_dict()
        d['apiKey'] = self.api_key
        return d
