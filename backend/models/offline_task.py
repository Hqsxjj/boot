from sqlalchemy import Column, String, Integer, Float, DateTime, Enum, func, Index
from datetime import datetime
from enum import Enum as PyEnum
from models.database import Base


class TaskStatus(PyEnum):
    """Enum for offline task status."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OfflineTask(Base):
    """Model for storing offline download tasks from 115 cloud."""
    __tablename__ = 'offline_tasks'
    
    id = Column(String(36), primary_key=True, unique=True, nullable=False)  # UUID
    p115_task_id = Column(String(255), nullable=True, unique=True)  # 115 API task ID
    source_url = Column(String, nullable=False)  # URL or magnet link
    save_cid = Column(String(255), nullable=False)  # Target folder CID in 115
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    progress = Column(Integer, default=0)  # 0-100 percentage
    speed = Column(Float, nullable=True)  # Current download speed (bytes/sec)
    requested_by = Column(String(255), nullable=False)  # Telegram user ID
    requested_chat = Column(String(255), nullable=False)  # Telegram chat ID
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_status', 'status'),
        Index('idx_requested_by', 'requested_by'),
        Index('idx_created_at', 'created_at'),
        Index('idx_p115_task_id', 'p115_task_id'),
        Index('idx_save_cid', 'save_cid'),
    )
    
    def to_dict(self) -> dict:
        """Convert task to dictionary."""
        return {
            'id': self.id,
            'p115TaskId': self.p115_task_id,
            'sourceUrl': self.source_url,
            'saveCid': self.save_cid,
            'status': self.status.value if self.status else 'pending',
            'progress': self.progress,
            'speed': self.speed,
            'requestedBy': self.requested_by,
            'requestedChat': self.requested_chat,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f'<OfflineTask(id={self.id}, status={self.status}, p115_task_id={self.p115_task_id})>'
