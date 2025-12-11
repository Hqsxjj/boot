import os
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class OfflineTaskPoller:
    """Background task poller for syncing offline tasks."""
    
    def __init__(self, offline_task_service, interval: int = 60):
        """
        Initialize poller.
        
        Args:
            offline_task_service: OfflineTaskService instance
            interval: Poll interval in seconds (default: 60)
        """
        self.offline_task_service = offline_task_service
        self.interval = interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the polling thread."""
        if self.running:
            logger.warning('Poller already running')
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        logger.info(f'Started offline task poller with {self.interval}s interval')
    
    def stop(self):
        """Stop the polling thread."""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info('Stopped offline task poller')
    
    def _poll_loop(self):
        """Main polling loop."""
        while self.running:
            try:
                # Sync all tasks
                result = self.offline_task_service.sync_all()
                if result.get('success'):
                    logger.debug(f'Sync completed: {result.get("synced")} synced, {result.get("failed")} failed')
                else:
                    logger.warning(f'Sync failed: {result.get("error")}')
            except Exception as e:
                logger.error(f'Polling error: {str(e)}')
            
            # Wait before next poll
            time.sleep(self.interval)


def create_task_poller(offline_task_service) -> OfflineTaskPoller:
    """
    Create and configure task poller from environment.
    
    Args:
        offline_task_service: OfflineTaskService instance
    
    Returns:
        Configured OfflineTaskPoller instance
    """
    interval = int(os.environ.get('OFFLINE_TASK_POLL_INTERVAL', '60'))
    return OfflineTaskPoller(offline_task_service, interval=interval)
