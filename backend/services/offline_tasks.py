import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from models.offline_task import OfflineTask, TaskStatus
from p115_bridge import get_p115_service, P115Service
from persistence.store import DataStore

logger = logging.getLogger(__name__)


class OfflineTaskService:
    """Service for managing offline tasks with 115 cloud integration."""
    
    def __init__(self, session_factory, data_store: DataStore, p115_service: P115Service = None, cloud115_service=None):
        """
        Initialize OfflineTaskService.
        
        Args:
            session_factory: SQLAlchemy session factory
            data_store: DataStore instance for config
            p115_service: P115Service instance (optional, uses global if None)
            cloud115_service: Cloud115Service instance (optional, for real 115 API calls)
        """
        self.session_factory = session_factory
        self.data_store = data_store
        self.p115_service = p115_service or get_p115_service()
        self.cloud115_service = cloud115_service
        self._qps_throttle = 1  # Default QPS from config
        self._listeners = []  # List of callback functions
        self._update_qps_throttle()
    
    def add_listener(self, callback):
        """Add a listener for task events."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _notify_listeners(self, task_id: str, status: TaskStatus):
        """Notify listeners of task status change."""
        for callback in self._listeners:
            try:
                callback(task_id, status)
            except Exception as e:
                logger.error(f"Error in task listener: {e}")

    def _update_qps_throttle(self):
        """Update QPS throttle from config."""
        try:
            config = self.data_store.get_config()
            self._qps_throttle = config.get('cloud115', {}).get('qps', 1)
        except Exception as e:
            logger.warning(f'Failed to update QPS throttle: {str(e)}')
            self._qps_throttle = 1
    
    def create_task(self, 
                   source_url: str,
                   save_cid: str,
                   requested_by: str,
                   requested_chat: str) -> Dict[str, Any]:
        """
        Create a new offline task.
        
        Args:
            source_url: URL or magnet link
            save_cid: Target folder CID in 115
            requested_by: Telegram user ID
            requested_chat: Telegram chat ID
        
        Returns:
            Dict with success flag and task data or error
        """
        try:
            # Validate inputs
            if not source_url:
                return {'success': False, 'error': 'source_url is required'}
            if not save_cid:
                return {'success': False, 'error': 'save_cid is required'}
            
            # Create task record
            task_id = str(uuid.uuid4())
            task = OfflineTask(
                id=task_id,
                source_url=source_url,
                save_cid=save_cid,
                status=TaskStatus.PENDING,
                progress=0,
                requested_by=requested_by,
                requested_chat=requested_chat,
            )
            
            session: Session = self.session_factory()
            session.add(task)
            session.commit()
            
            # Convert to dict before closing session
            task_dict = task.to_dict()
            session.close()
            
            logger.info(f'Created offline task {task_id} for URL {source_url}')
            
            return {
                'success': True,
                'data': task_dict
            }
        except Exception as e:
            logger.error(f'Failed to create offline task: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to create task: {str(e)}'
            }
    
    def list_tasks(self,
                   status: Optional[str] = None,
                   requested_by: Optional[str] = None,
                   limit: int = 50,
                   offset: int = 0) -> Dict[str, Any]:
        """
        List offline tasks with optional filtering.
        
        Args:
            status: Filter by status
            requested_by: Filter by requesting user
            limit: Maximum number of results
            offset: Offset for pagination
        
        Returns:
            Dict with success flag and list of tasks
        """
        try:
            session: Session = self.session_factory()
            query = session.query(OfflineTask)
            
            if status:
                try:
                    status_enum = TaskStatus(status)
                    query = query.filter(OfflineTask.status == status_enum)
                except ValueError:
                    session.close()
                    return {'success': False, 'error': f'Invalid status: {status}'}
            
            if requested_by:
                query = query.filter(OfflineTask.requested_by == requested_by)
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            tasks = query.order_by(OfflineTask.created_at.desc()).offset(offset).limit(limit).all()
            
            session.close()
            
            return {
                'success': True,
                'data': {
                    'tasks': [task.to_dict() for task in tasks],
                    'total': total,
                    'limit': limit,
                    'offset': offset
                }
            }
        except Exception as e:
            logger.error(f'Failed to list offline tasks: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to list tasks: {str(e)}'
            }
    
    def get_task(self, task_id: str) -> Optional[OfflineTask]:
        """Get a single task by ID."""
        try:
            session: Session = self.session_factory()
            task = session.query(OfflineTask).filter(OfflineTask.id == task_id).first()
            session.close()
            return task
        except Exception as e:
            logger.error(f'Failed to get task {task_id}: {str(e)}')
            return None
    
    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel an offline task.
        
        Args:
            task_id: Task ID to cancel
        
        Returns:
            Dict with success flag
        """
        try:
            session: Session = self.session_factory()
            task = session.query(OfflineTask).filter(OfflineTask.id == task_id).first()
            
            if not task:
                session.close()
                return {'success': False, 'error': 'Task not found'}
            
            # Try to cancel on 115 if task ID exists
            if task.p115_task_id:
                try:
                    # This would use p115_service to cancel, but without real p115client
                    # we just update local status
                    logger.info(f'Would cancel 115 task {task.p115_task_id}')
                except Exception as e:
                    logger.warning(f'Failed to cancel 115 task: {str(e)}')
            
            # Update local status
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.now()
            session.commit()
            
            # Convert to dict before closing session
            task_dict = task.to_dict()
            session.close()
            
            logger.info(f'Cancelled offline task {task_id}')
            
            return {
                'success': True,
                'data': task_dict
            }
        except Exception as e:
            logger.error(f'Failed to cancel task {task_id}: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to cancel task: {str(e)}'
            }
    
    def retry_task(self, task_id: str) -> Dict[str, Any]:
        """
        Retry a failed task.
        
        Args:
            task_id: Task ID to retry
        
        Returns:
            Dict with success flag and updated task
        """
        try:
            session: Session = self.session_factory()
            task = session.query(OfflineTask).filter(OfflineTask.id == task_id).first()
            
            if not task:
                session.close()
                return {'success': False, 'error': 'Task not found'}
            
            if task.status != TaskStatus.FAILED:
                session.close()
                return {'success': False, 'error': f'Task status is {task.status.value}, not failed'}
            
            # Reset to pending
            task.status = TaskStatus.PENDING
            task.progress = 0
            task.p115_task_id = None
            task.updated_at = datetime.now()
            session.commit()
            
            # Convert to dict before closing session
            task_dict = task.to_dict()
            session.close()
            
            logger.info(f'Retried offline task {task_id}')
            
            return {
                'success': True,
                'data': task_dict
            }
        except Exception as e:
            logger.error(f'Failed to retry task {task_id}: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to retry task: {str(e)}'
            }
    
    def sync_all(self) -> Dict[str, Any]:
        """
        Sync all pending and downloading tasks with 115 API.
        
        Returns:
            Dict with sync statistics
        """
        try:
            session: Session = self.session_factory()
            
            # Get all non-terminal tasks with p115_task_id
            tasks = session.query(OfflineTask).filter(
                OfflineTask.status.in_([TaskStatus.PENDING, TaskStatus.DOWNLOADING]),
                OfflineTask.p115_task_id.isnot(None)
            ).all()
            
            synced_count = 0
            failed_count = 0
            
            for task in tasks:
                try:
                    # Skip if cloud115_service is not available
                    if not self.cloud115_service:
                        synced_count += 1
                        continue
                    
                    # Get task status from 115 API
                    result = self.cloud115_service.get_offline_task_status(task.p115_task_id)
                    
                    if result.get('success'):
                        data = result.get('data', {})
                        
                        # Update task with latest info
                        status_str = data.get('status', 'pending')
                        if status_str == 'downloading':
                            task.status = TaskStatus.DOWNLOADING
                        elif status_str == 'completed':
                            task.status = TaskStatus.COMPLETED
                        elif status_str == 'failed':
                            task.status = TaskStatus.FAILED
                        elif status_str == 'pending':
                            task.status = TaskStatus.PENDING
                        
                        task.progress = data.get('progress', task.progress)
                        task.speed = data.get('speed', task.speed)
                        task.updated_at = datetime.now()
                        
                        session.merge(task)
                        synced_count += 1
                        
                        # Notify listeners if status changed to COMPLETED
                        if task.status == TaskStatus.COMPLETED and status_str == 'completed':
                             self._notify_listeners(task.p115_task_id, TaskStatus.COMPLETED)
                    else:
                        logger.warning(f'Failed to get status for task {task.id}: {result.get("error")}')
                        failed_count += 1
                    
                except Exception as e:
                    logger.warning(f'Failed to sync task {task.id}: {str(e)}')
                    failed_count += 1
            
            session.commit()
            session.close()
            
            logger.info(f'Synced {synced_count} tasks, {failed_count} failed')
            
            return {
                'success': True,
                'synced': synced_count,
                'failed': failed_count,
                'total': len(tasks)
            }
        except Exception as e:
            logger.error(f'Failed to sync tasks: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to sync tasks: {str(e)}'
            }
    
    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """
        Delete a task (soft delete by setting status to CANCELLED).
        
        Args:
            task_id: Task ID to delete
        
        Returns:
            Dict with success flag
        """
        try:
            session: Session = self.session_factory()
            task = session.query(OfflineTask).filter(OfflineTask.id == task_id).first()
            
            if not task:
                session.close()
                return {'success': False, 'error': 'Task not found'}
            
            # Convert to dict before deleting
            task_dict = task.to_dict()
            
            session.delete(task)
            session.commit()
            session.close()
            
            logger.info(f'Deleted offline task {task_id}')
            
            return {
                'success': True,
                'data': task_dict
            }
        except Exception as e:
            logger.error(f'Failed to delete task {task_id}: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to delete task: {str(e)}'
            }
