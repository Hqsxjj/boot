"""
Organize Worker Service

Background worker for media organize tasks with QPS rate limiting.
Respects cloud API rate limits to avoid being blocked.
"""
import time
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from utils.logger import TaskLogger


class QPSLimiter:
    """
    QPS (Queries Per Second) rate limiter.
    
    Ensures minimum time interval between API calls to respect rate limits.
    Thread-safe for concurrent access.
    """
    
    def __init__(self, qps: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            qps: Maximum queries per second (default 1.0)
        """
        self.qps = qps
        self.min_interval = 1.0 / qps if qps > 0 else 1.0
        self.last_call = 0.0
        self.lock = threading.Lock()
    
    def wait(self):
        """
        Wait if needed to respect QPS limit.
        Call this before each API request.
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            
            self.last_call = time.time()
    
    def update_qps(self, qps: float):
        """Update QPS limit dynamically."""
        with self.lock:
            self.qps = qps
            self.min_interval = 1.0 / qps if qps > 0 else 1.0


@dataclass
class OrganizeItem:
    """Single item to organize"""
    file_id: str
    original_name: str
    new_name: str
    target_dir: Optional[str] = None
    status: str = 'pending'  # pending, processing, completed, failed
    error: Optional[str] = None


@dataclass
class OrganizeTask:
    """Organize task containing multiple items"""
    task_id: str
    cloud_type: str  # '115' or '123'
    items: List[OrganizeItem] = field(default_factory=list)
    status: str = 'pending'  # pending, running, completed, failed
    progress: int = 0
    current_item: str = ''
    completed_count: int = 0
    failed_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'taskId': self.task_id,
            'cloudType': self.cloud_type,
            'status': self.status,
            'progress': self.progress,
            'currentItem': self.current_item,
            'totalItems': len(self.items),
            'completedCount': self.completed_count,
            'failedCount': self.failed_count,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'startedAt': self.started_at.isoformat() if self.started_at else None,
            'completedAt': self.completed_at.isoformat() if self.completed_at else None,
            'error': self.error,
            'items': [
                {
                    'fileId': item.file_id,
                    'originalName': item.original_name,
                    'newName': item.new_name,
                    'targetDir': item.target_dir,
                    'status': item.status,
                    'error': item.error
                }
                for item in self.items
            ]
        }


class OrganizeWorker:
    """
    Background worker for organize tasks.
    
    Features:
    - QPS rate limiting per cloud type
    - Background thread execution
    - Progress tracking and logging
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # Task storage
        self._tasks: Dict[str, OrganizeTask] = {}
        self._lock = threading.Lock()
        
        # QPS limiters per cloud type
        self._limiters = {
            '115': QPSLimiter(qps=1.0),  # 115 default 1 QPS
            '123': QPSLimiter(qps=2.0),  # 123 default 2 QPS
        }
        
        # Cloud services (set externally)
        self.cloud115_service = None
        self.cloud123_service = None
        self.media_organizer = None
    
    def set_services(self, cloud115_service=None, cloud123_service=None, media_organizer=None):
        """Set cloud services for API calls."""
        self.cloud115_service = cloud115_service
        self.cloud123_service = cloud123_service
        self.media_organizer = media_organizer
    
    def set_qps(self, cloud_type: str, qps: float):
        """Update QPS limit for a cloud type."""
        if cloud_type in self._limiters:
            self._limiters[cloud_type].update_qps(qps)
    
    def create_task(self, cloud_type: str, items: List[Dict[str, Any]]) -> OrganizeTask:
        """
        Create a new organize task.
        
        Args:
            cloud_type: '115' or '123'
            items: List of dicts with fileId, originalName, newName, targetDir
            
        Returns:
            OrganizeTask instance
        """
        import uuid
        task_id = str(uuid.uuid4())[:8]
        
        organize_items = [
            OrganizeItem(
                file_id=item['fileId'],
                original_name=item.get('originalName', ''),
                new_name=item['newName'],
                target_dir=item.get('targetDir')
            )
            for item in items
        ]
        
        task = OrganizeTask(
            task_id=task_id,
            cloud_type=cloud_type,
            items=organize_items
        )
        
        with self._lock:
            self._tasks[task_id] = task
        
        return task
    
    def start_task(self, task_id: str) -> bool:
        """
        Start executing a task in background thread.
        
        Args:
            task_id: Task ID to start
            
        Returns:
            True if started, False if task not found or already running
        """
        task = self.get_task(task_id)
        if not task:
            return False
        
        if task.status != 'pending':
            return False
        
        thread = threading.Thread(
            target=self._execute_task,
            args=(task,),
            daemon=True
        )
        thread.start()
        return True
    
    def _execute_task(self, task: OrganizeTask):
        """Execute organize task with QPS limiting."""
        task_log = TaskLogger('网盘整理')
        task_log.start(f'批量整理 {len(task.items)} 个文件 ({task.cloud_type})')
        
        task.status = 'running'
        task.started_at = datetime.now()
        
        limiter = self._limiters.get(task.cloud_type)
        if not limiter:
            limiter = QPSLimiter(qps=1.0)
        
        total = len(task.items)
        
        for idx, item in enumerate(task.items):
            try:
                # Update progress
                task.current_item = item.original_name
                task.progress = int((idx / total) * 100)
                
                task_log.log(f'[{idx + 1}/{total}] 处理: {item.original_name}')
                
                # Wait for rate limit
                limiter.wait()
                
                # Execute organize
                item.status = 'processing'
                result = self._organize_single(task.cloud_type, item)
                
                if result.get('success'):
                    item.status = 'completed'
                    task.completed_count += 1
                    task_log.log(f'[{idx + 1}/{total}] ✅ 完成: {item.new_name}')
                else:
                    item.status = 'failed'
                    item.error = result.get('error', '未知错误')
                    task.failed_count += 1
                    task_log.log(f'[{idx + 1}/{total}] ❌ 失败: {item.error}')
                    
            except Exception as e:
                item.status = 'failed'
                item.error = str(e)
                task.failed_count += 1
                task_log.log(f'[{idx + 1}/{total}] ❌ 异常: {e}')
        
        # Complete task
        task.progress = 100
        task.current_item = ''
        task.completed_at = datetime.now()
        
        if task.failed_count == 0:
            task.status = 'completed'
            task_log.success(f'批量整理完成: {task.completed_count}/{total} 成功')
        elif task.completed_count == 0:
            task.status = 'failed'
            task.error = f'所有 {total} 个文件整理失败'
            task_log.failure(task.error)
        else:
            task.status = 'completed'
            task_log.success(f'批量整理完成: {task.completed_count} 成功, {task.failed_count} 失败')
    
    def _organize_single(self, cloud_type: str, item: OrganizeItem) -> Dict[str, Any]:
        """Organize a single file."""
        if cloud_type == '115':
            if not self.cloud115_service:
                return {'success': False, 'error': '115 服务未初始化'}
            
            # Rename
            rename_result = self.cloud115_service.rename_file(item.file_id, item.new_name)
            if not rename_result.get('success'):
                return rename_result
            
            # Move if target_dir specified
            if item.target_dir and self.media_organizer:
                target_cid = self.media_organizer._ensure_115_directory(item.target_dir)
                if not target_cid:
                    return {'success': False, 'error': f'无法创建目录: {item.target_dir}'}
                
                move_result = self.cloud115_service.move_file(item.file_id, target_cid)
                if not move_result.get('success'):
                    return move_result
            
            return {'success': True}
            
        elif cloud_type == '123':
            if not self.cloud123_service:
                return {'success': False, 'error': '123 服务未初始化'}
            
            rename_result = self.cloud123_service.rename_file(item.file_id, item.new_name)
            if not rename_result.get('success'):
                return rename_result
            
            if item.target_dir and self.media_organizer:
                target_id = self.media_organizer._ensure_123_directory(item.target_dir)
                if not target_id:
                    return {'success': False, 'error': f'无法创建目录: {item.target_dir}'}
                
                move_result = self.cloud123_service.move_file(item.file_id, target_id)
                if not move_result.get('success'):
                    return move_result
            
            return {'success': True}
        
        return {'success': False, 'error': f'不支持的云盘类型: {cloud_type}'}
    
    def get_task(self, task_id: str) -> Optional[OrganizeTask]:
        """Get task by ID."""
        with self._lock:
            return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks as dicts."""
        with self._lock:
            return [task.to_dict() for task in self._tasks.values()]
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending task.
        Running tasks cannot be cancelled.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == 'pending':
                task.status = 'failed'
                task.error = '已取消'
                return True
        return False
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Remove old completed/failed tasks."""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._lock:
            to_remove = [
                tid for tid, task in self._tasks.items()
                if task.status in ('completed', 'failed')
                and task.completed_at and task.completed_at < cutoff
            ]
            for tid in to_remove:
                del self._tasks[tid]


# Global singleton
_organize_worker: Optional[OrganizeWorker] = None


def get_organize_worker() -> OrganizeWorker:
    """Get organize worker singleton."""
    global _organize_worker
    if _organize_worker is None:
        _organize_worker = OrganizeWorker()
    return _organize_worker
