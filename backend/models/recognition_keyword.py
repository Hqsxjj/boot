# models/recognition_keyword.py
# 识别词累积存储模型

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text
from sqlalchemy.sql import func
from .database import AppDataBase


class RecognitionKeyword(AppDataBase):
    """Model for storing accumulated recognition keywords from AI parsing."""
    __tablename__ = 'recognition_keywords'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(500), nullable=False, index=True)  # 原始文件名中的关键词
    normalized = Column(String(500), nullable=False, index=True)  # 规范化后的名称
    media_type = Column(String(50), nullable=False, default='movie')  # movie/tv
    match_count = Column(Integer, default=1)  # 匹配次数
    tmdb_id = Column(String(50))  # 关联的 TMDB ID
    source = Column(String(100), default='ai')  # 来源: ai / manual / import
    extra_info = Column(Text)  # JSON 格式的额外信息
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f'<RecognitionKeyword(keyword={self.keyword}, normalized={self.normalized}, count={self.match_count})>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'keyword': self.keyword,
            'normalized': self.normalized,
            'mediaType': self.media_type,
            'matchCount': self.match_count,
            'tmdbId': self.tmdb_id,
            'source': self.source,
            'extraInfo': self.extra_info,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
