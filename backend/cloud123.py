
# backend/cloud123.py

import logging
from typing import Dict, Any, List, Optional
import time

logger = logging.getLogger(__name__)

class Cloud123Client:
    """
    Stub client for 123 Cloud.
    This replaces the missing 'cloud123' library.
    """

    def __init__(self, token: Optional[Dict] = None, cookies: Optional[Dict] = None):
        self.token = token
        self.cookies = cookies
        logger.info("Initialized Cloud123Client stub")

    def list_files(self, dir_id: str) -> List[Dict[str, Any]]:
        """List files in directory."""
        logger.info(f"Mock listing files for dir_id: {dir_id}")
        # Return some dummy data to verify interface works
        return [
            {
                'id': '1',
                'name': 'Welcome to 123 Cloud (Stub).txt',
                'is_dir': False,
                'timestamp': time.time()
            },
            {
                'id': '2',
                'name': 'Test Folder',
                'is_dir': True,
                'timestamp': time.time()
            }
        ]

    def rename(self, file_id: str, new_name: str) -> bool:
        """Rename file."""
        logger.info(f"Mock rename file {file_id} to {new_name}")
        return True

    def move(self, file_id: str, target_dir_id: str) -> bool:
        """Move file."""
        logger.info(f"Mock move file {file_id} to {target_dir_id}")
        return True

    def delete(self, file_id: str) -> bool:
        """Delete file."""
        logger.info(f"Mock delete file {file_id}")
        return True

    def get_download_url(self, file_id: str) -> str:
        """Get download URL."""
        logger.info(f"Mock get download url for {file_id}")
        return "https://example.com/mock-download-url"

    def add_offline_task(self, url: str, dir_id: str) -> Dict[str, Any]:
        """Add offline download task."""
        logger.info(f"Mock add offline task {url} to {dir_id}")
        return {'task_id': 'mock-task-123'}

    def list_offline_tasks(self) -> List[Dict[str, Any]]:
        """List offline tasks."""
        logger.info("Mock list offline tasks")
        return [
            {
                'task_id': 'mock-task-123',
                'status': 'downloading',
                'progress': 45.5,
                'speed': 1024 * 1024 * 2 # 2 MB/s
            }
        ]

    def get_user_info(self) -> Dict[str, Any]:
        """Get user info."""
        return {'username': 'Mock User', 'quota': 1024 * 1024 * 1024 * 10}
