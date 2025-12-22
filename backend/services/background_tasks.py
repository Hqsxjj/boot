"""
Background Task Service

Manages long-running tasks that should continue even if the frontend is refreshed.
All progress is logged to the console via Python logging.
"""
import threading
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BackgroundTask:
    """Represents a single background task."""
    
    def __init__(self, task_id: str, task_type: str, description: str):
        self.task_id = task_id
        self.task_type = task_type
        self.description = description
        self.status = TaskStatus.PENDING
        self.progress = 0
        self.current_item = ""
        self.total_items = 0
        self.completed_items = 0
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'taskId': self.task_id,
            'taskType': self.task_type,
            'description': self.description,
            'status': self.status.value,
            'progress': self.progress,
            'currentItem': self.current_item,
            'totalItems': self.total_items,
            'completedItems': self.completed_items,
            'error': self.error,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'startedAt': self.started_at.isoformat() if self.started_at else None,
            'completedAt': self.completed_at.isoformat() if self.completed_at else None,
        }


class BackgroundTaskService:
    """
    Service for managing background tasks.
    
    Tasks run in separate threads and continue even if frontend disconnects.
    Progress is logged to the backend console.
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
        self._tasks: Dict[str, BackgroundTask] = {}
        self._lock = threading.Lock()
        
    def create_task(self, task_type: str, description: str) -> BackgroundTask:
        """Create a new background task."""
        import uuid
        task_id = str(uuid.uuid4())[:8]
        task = BackgroundTask(task_id, task_type, description)
        
        with self._lock:
            self._tasks[task_id] = task
            
        logger.info(f"[后台任务] 创建任务 [{task_id}]: {description}")
        return task
    
    def run_task(self, task: BackgroundTask, func: Callable, *args, **kwargs):
        """
        Run a task in a background thread.
        
        The function should call task.update_progress() periodically.
        """
        def wrapper():
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            logger.info(f"[后台任务] 开始执行 [{task.task_id}]: {task.description}")
            
            try:
                result = func(task, *args, **kwargs)
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.completed_at = datetime.now()
                logger.info(f"[后台任务] 完成 [{task.task_id}]: {task.description}")
            except Exception as e:
                task.error = str(e)
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                logger.error(f"[后台任务] 失败 [{task.task_id}]: {e}")
                
        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        return task
    
    def update_progress(self, task: BackgroundTask, current: int, total: int, current_item: str = ""):
        """Update task progress and log it."""
        task.completed_items = current
        task.total_items = total
        task.current_item = current_item
        task.progress = int((current / total) * 100) if total > 0 else 0
        
        logger.info(f"[后台任务] [{task.task_id}] 进度: {current}/{total} ({task.progress}%) - {current_item}")
    
    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """Get task by ID."""
        with self._lock:
            return self._tasks.get(task_id)
    
    def get_running_tasks(self, task_type: str = None) -> list:
        """Get all running tasks, optionally filtered by type."""
        with self._lock:
            tasks = [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]
            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]
            return [t.to_dict() for t in tasks]
    
    def get_all_tasks(self) -> list:
        """Get all tasks."""
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Remove completed tasks older than max_age_hours."""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._lock:
            to_remove = [
                tid for tid, task in self._tasks.items()
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
                and task.completed_at and task.completed_at < cutoff
            ]
            for tid in to_remove:
                del self._tasks[tid]


# Global singleton instance
_bg_service: Optional[BackgroundTaskService] = None

def get_background_service() -> BackgroundTaskService:
    global _bg_service
    if _bg_service is None:
        _bg_service = BackgroundTaskService()
    return _bg_service
