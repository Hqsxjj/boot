"""
整理日志服务 - 记录详细的文件整理过程日志

日志格式: 源文件目录/原文件名 》 重命名后名称 》 整理后存放文件路径 #成功/失败
"""
import logging
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import deque

logger = logging.getLogger(__name__)


class OrganizeLogEntry:
    """单条整理日志条目"""
    
    def __init__(
        self,
        source_dir: str,
        original_name: str,
        new_name: str,
        target_path: str,
        status: str,  # 'success' | 'failed'
        error: str = None,
        cloud_type: str = '115',
        timestamp: datetime = None
    ):
        self.source_dir = source_dir
        self.original_name = original_name
        self.new_name = new_name
        self.target_path = target_path
        self.status = status
        self.error = error
        self.cloud_type = cloud_type
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_dir': self.source_dir,
            'original_name': self.original_name,
            'new_name': self.new_name,
            'target_path': self.target_path,
            'status': self.status,
            'error': self.error,
            'cloud_type': self.cloud_type,
            'timestamp': self.timestamp.isoformat(),
            'formatted': self.format()
        }
    
    def format(self) -> str:
        """格式化为指定的日志格式"""
        result_tag = '成功' if self.status == 'success' else f'失败: {self.error or "未知错误"}'
        return f"{self.source_dir}/{self.original_name} 》 {self.new_name} 》 {self.target_path} #{result_tag}"


class OrganizeLogService:
    """
    整理日志服务 - 单例模式
    
    功能：
    - 记录整理过程日志
    - 提供日志查询
    - 支持滚动日志（最多保留1000条）
    """
    
    _instance = None
    _lock = threading.Lock()
    
    MAX_LOG_ENTRIES = 1000
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # 使用 deque 实现固定大小的滚动日志
        self._logs: deque = deque(maxlen=self.MAX_LOG_ENTRIES)
        self._log_lock = threading.Lock()
        
        logger.info('OrganizeLogService 初始化完成')
    
    def add_log(
        self,
        source_dir: str,
        original_name: str,
        new_name: str,
        target_path: str,
        status: str,
        error: str = None,
        cloud_type: str = '115'
    ) -> OrganizeLogEntry:
        """添加一条整理日志"""
        entry = OrganizeLogEntry(
            source_dir=source_dir,
            original_name=original_name,
            new_name=new_name,
            target_path=target_path,
            status=status,
            error=error,
            cloud_type=cloud_type
        )
        
        with self._log_lock:
            self._logs.append(entry)
        
        # 同时写入系统日志
        if status == 'success':
            logger.info(f'整理成功: {entry.format()}')
        else:
            logger.warning(f'整理失败: {entry.format()}')
        
        return entry
    
    def log_success(
        self,
        source_dir: str,
        original_name: str,
        new_name: str,
        target_path: str,
        cloud_type: str = '115'
    ) -> OrganizeLogEntry:
        """记录成功日志"""
        return self.add_log(
            source_dir=source_dir,
            original_name=original_name,
            new_name=new_name,
            target_path=target_path,
            status='success',
            cloud_type=cloud_type
        )
    
    def log_failure(
        self,
        source_dir: str,
        original_name: str,
        new_name: str,
        target_path: str,
        error: str,
        cloud_type: str = '115'
    ) -> OrganizeLogEntry:
        """记录失败日志"""
        return self.add_log(
            source_dir=source_dir,
            original_name=original_name,
            new_name=new_name,
            target_path=target_path,
            status='failed',
            error=error,
            cloud_type=cloud_type
        )
    
    def get_logs(self, limit: int = 100, since: datetime = None) -> List[Dict[str, Any]]:
        """获取日志列表（最新的在前）"""
        with self._log_lock:
            logs = list(self._logs)
        
        # 按时间倒序
        logs.reverse()
        
        # 筛选时间
        if since:
            logs = [log for log in logs if log.timestamp > since]
        
        # 限制数量
        logs = logs[:limit]
        
        return [log.to_dict() for log in logs]
    
    def get_recent_count(self, minutes: int = 60) -> Dict[str, int]:
        """获取最近N分钟的统计"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(minutes=minutes)
        
        with self._log_lock:
            recent = [log for log in self._logs if log.timestamp > cutoff]
        
        success_count = sum(1 for log in recent if log.status == 'success')
        failed_count = sum(1 for log in recent if log.status == 'failed')
        
        return {
            'total': len(recent),
            'success': success_count,
            'failed': failed_count,
            'minutes': minutes
        }
    
    def clear(self):
        """清空所有日志"""
        with self._log_lock:
            self._logs.clear()


# 全局单例
_organize_log_service: Optional[OrganizeLogService] = None


def get_organize_log_service() -> OrganizeLogService:
    """获取整理日志服务单例"""
    global _organize_log_service
    if _organize_log_service is None:
        _organize_log_service = OrganizeLogService()
    return _organize_log_service
