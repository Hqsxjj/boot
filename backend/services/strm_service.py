import uuid
import time
from persistence.store import DataStore
from typing import Dict, Any, List


class StrmService:
    """Service for handling STRM generation."""
    
    def __init__(self, store: DataStore):
        self.store = store
        self.tasks: Dict[str, Dict[str, Any]] = {}
    
    def _get_config(self) -> Dict[str, Any]:
        """Get STRM configuration from store."""
        try:
            config = self.store.get_config()
            return config.get('strm', {})
        except Exception:
            return {}
    
    def generate_strm(self, strm_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate STRM files for the specified provider."""
        if strm_type not in ['115', '123', 'openlist']:
            return {
                'success': False,
                'data': {'error': f'Invalid STRM type: {strm_type}'}
            }
        
        # Create a task
        task_id = str(uuid.uuid4())
        task = {
            'id': task_id,
            'type': strm_type,
            'status': 'running',
            'progress': 0,
            'created_at': time.time(),
            'config': config
        }
        self.tasks[task_id] = task
        
        # In a real implementation, this would spawn a background job
        # For now, we just simulate completion
        task['status'] = 'completed'
        task['progress'] = 100
        
        return {
            'success': True,
            'data': {
                'jobId': task_id,
                'status': task['status'],
                'type': strm_type
            }
        }
    
    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all STRM generation tasks."""
        return list(self.tasks.values())
    
    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get a specific task by ID."""
        return self.tasks.get(task_id, {})
