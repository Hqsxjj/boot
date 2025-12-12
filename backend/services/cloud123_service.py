import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from services.secret_store import SecretStore

logger = logging.getLogger(__name__)


class Cloud123Service:
    """Service for interacting with 123 cloud via OAuth or cookies."""
    
    def __init__(self, secret_store: SecretStore):
        """
        Initialize Cloud123Service.
        
        Args:
            secret_store: SecretStore instance for retrieving tokens
        """
        self.secret_store = secret_store
        self._client = None
        
        try:
            import cloud123
            self.cloud123 = cloud123
        except ImportError:
            self.cloud123 = None
            logger.warning('cloud123 not installed, 123 operations will be mocked')
    
    def _get_authenticated_client(self):
        """Get or create an authenticated cloud123 client instance."""
        if not self.cloud123:
            raise ImportError('cloud123 not installed')
        
        # Try to get token first (OAuth)
        token_json = self.secret_store.get_secret('cloud123_token')
        if token_json:
            try:
                token = json.loads(token_json)
                if hasattr(self.cloud123, 'Cloud123Client'):
                    client = self.cloud123.Cloud123Client(token=token)
                    return client
            except json.JSONDecodeError:
                logger.warning('Invalid token format in secret store')
        
        # Fall back to cookies if available
        cookies_json = self.secret_store.get_secret('cloud123_cookies')
        if not cookies_json:
            raise ValueError('No 123 token or cookies found in secret store')
        
        try:
            cookies = json.loads(cookies_json)
        except json.JSONDecodeError:
            raise ValueError('Invalid cookies format in secret store')
        
        # Create client with cookies
        if hasattr(self.cloud123, 'Cloud123Client'):
            client = self.cloud123.Cloud123Client(cookies=cookies)
            return client
        else:
            raise ImportError('cloud123.Cloud123Client not available')
    
    def list_directory(self, dir_id: str = '/') -> Dict[str, Any]:
        """
        List directory contents from 123 cloud.
        
        Args:
            dir_id: Directory ID (path), defaults to '/' for root
        
        Returns:
            Dict with success flag and list of entries
        """
        try:
            client = self._get_authenticated_client()
            
            # Get directory listing
            if hasattr(client, 'list_files'):
                entries = client.list_files(dir_id)
            elif hasattr(client, 'fs') and hasattr(client.fs, 'listdir'):
                entries = client.fs.listdir(dir_id)
            else:
                return {
                    'success': True,
                    'data': []
                }
            
            # Transform entries to match frontend format
            result = []
            for entry in entries:
                # Extract fields with various possible attribute names
                entry_id = getattr(entry, 'id', None) or getattr(entry, 'file_id', None) or getattr(entry, 'path', None)
                entry_name = getattr(entry, 'name', None) or getattr(entry, 'file_name', None)
                is_directory = getattr(entry, 'is_dir', None) or getattr(entry, 'is_directory', None) or getattr(entry, 'type', None) == 'dir'
                
                # Get timestamp
                timestamp = getattr(entry, 'timestamp', None) or getattr(entry, 'modified_time', None) or getattr(entry, 'mtime', None)
                if timestamp:
                    try:
                        if isinstance(timestamp, (int, float)):
                            date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                        else:
                            date_str = str(timestamp)[:10]
                    except:
                        date_str = datetime.now().strftime('%Y-%m-%d')
                else:
                    date_str = datetime.now().strftime('%Y-%m-%d')
                
                if entry_id and entry_name:
                    result.append({
                        'id': str(entry_id),
                        'name': entry_name,
                        'children': bool(is_directory),
                        'date': date_str
                    })
            
            return {
                'success': True,
                'data': result
            }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'Failed to list directory: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'Failed to list directory {dir_id}: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to list directory: {str(e)}'
            }
    
    def rename_file(self, file_id: str, new_name: str) -> Dict[str, Any]:
        """
        Rename a file or folder on 123 cloud.
        
        Args:
            file_id: File or folder ID
            new_name: New name
        
        Returns:
            Dict with success flag
        """
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'rename'):
                client.rename(file_id, new_name)
            elif hasattr(client, 'fs') and hasattr(client.fs, 'rename'):
                client.fs.rename(file_id, new_name)
            else:
                return {
                    'success': False,
                    'error': 'Rename operation not supported'
                }
            
            return {
                'success': True,
                'data': {
                    'fileId': file_id,
                    'newName': new_name
                }
            }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'Failed to rename file: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'Failed to rename file {file_id}: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to rename: {str(e)}'
            }
    
    def move_file(self, file_id: str, target_dir_id: str) -> Dict[str, Any]:
        """
        Move a file or folder to another directory on 123 cloud.
        
        Args:
            file_id: File or folder ID
            target_dir_id: Target directory ID
        
        Returns:
            Dict with success flag
        """
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'move'):
                client.move(file_id, target_dir_id)
            elif hasattr(client, 'fs') and hasattr(client.fs, 'move'):
                client.fs.move(file_id, target_dir_id)
            else:
                return {
                    'success': False,
                    'error': 'Move operation not supported'
                }
            
            return {
                'success': True,
                'data': {
                    'fileId': file_id,
                    'targetDirId': target_dir_id
                }
            }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'Failed to move file: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'Failed to move file {file_id}: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to move: {str(e)}'
            }
    
    def delete_file(self, file_id: str) -> Dict[str, Any]:
        """
        Delete a file or folder from 123 cloud.
        
        Args:
            file_id: File or folder ID
        
        Returns:
            Dict with success flag
        """
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'delete'):
                client.delete(file_id)
            elif hasattr(client, 'fs') and hasattr(client.fs, 'delete'):
                client.fs.delete(file_id)
            else:
                return {
                    'success': False,
                    'error': 'Delete operation not supported'
                }
            
            return {
                'success': True,
                'data': {
                    'fileId': file_id
                }
            }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'Failed to delete file: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'Failed to delete file {file_id}: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to delete: {str(e)}'
            }
    
    def get_download_link(self, file_id: str) -> Dict[str, Any]:
        """
        Get direct download link for a file.
        
        Args:
            file_id: File ID
        
        Returns:
            Dict with success flag and download URL
        """
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'get_download_url'):
                url = client.get_download_url(file_id)
            elif hasattr(client, 'fs') and hasattr(client.fs, 'get_url'):
                url = client.fs.get_url(file_id)
            else:
                return {
                    'success': False,
                    'error': 'Download link operation not supported'
                }
            
            return {
                'success': True,
                'data': {
                    'fileId': file_id,
                    'url': url
                }
            }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'Failed to get download link: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'Failed to get download link for {file_id}: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to get download link: {str(e)}'
            }
    
    def create_offline_task(self, source_url: str, save_dir_id: str) -> Dict[str, Any]:
        """
        Create an offline download task on 123 cloud.
        
        Args:
            source_url: URL or magnet link to download
            save_dir_id: Target directory ID
        
        Returns:
            Dict with success flag and task ID from 123
        """
        try:
            client = self._get_authenticated_client()
            
            # Try various possible method names
            if hasattr(client, 'add_offline_task'):
                result = client.add_offline_task(source_url, save_dir_id)
            elif hasattr(client, 'offline') and hasattr(client.offline, 'add_url'):
                result = client.offline.add_url(source_url, save_dir_id)
            elif hasattr(client, 'offline_add'):
                result = client.offline_add(source_url, save_dir_id)
            else:
                return {
                    'success': False,
                    'error': 'Offline task creation not supported'
                }
            
            # Extract task ID from result
            if isinstance(result, dict):
                task_id = result.get('task_id') or result.get('info_hash') or result.get('id')
            else:
                task_id = str(result)
            
            return {
                'success': True,
                'data': {
                    'p123TaskId': task_id,
                    'sourceUrl': source_url,
                    'saveDirId': save_dir_id
                }
            }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'Failed to create offline task: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'Failed to create offline task: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to create offline task: {str(e)}'
            }
    
    def get_offline_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of an offline task from 123 cloud.
        
        Args:
            task_id: Task ID from 123
        
        Returns:
            Dict with task status, progress, and speed
        """
        try:
            client = self._get_authenticated_client()
            
            # Try various possible method names
            if hasattr(client, 'list_offline_tasks'):
                tasks = client.list_offline_tasks()
            elif hasattr(client, 'offline') and hasattr(client.offline, 'list'):
                tasks = client.offline.list()
            else:
                return {
                    'success': False,
                    'error': 'Offline task status not supported'
                }
            
            # Find the task by ID
            task_info = None
            for task in tasks:
                if isinstance(task, dict):
                    if task.get('task_id') == task_id or task.get('info_hash') == task_id or task.get('id') == task_id:
                        task_info = task
                        break
                elif hasattr(task, 'task_id'):
                    if getattr(task, 'task_id', None) == task_id or getattr(task, 'info_hash', None) == task_id:
                        task_info = {
                            'status': getattr(task, 'status', None),
                            'progress': getattr(task, 'progress', None) or getattr(task, 'percentDone', None),
                            'speed': getattr(task, 'speed', None) or getattr(task, 'rateDownload', None),
                        }
                        break
            
            if not task_info:
                return {
                    'success': False,
                    'error': f'Task {task_id} not found'
                }
            
            # Map status to our enum
            status_map = {
                '1': 'downloading',
                '2': 'completed',
                '-1': 'failed',
                'downloading': 'downloading',
                'completed': 'completed',
                'failed': 'failed',
                'seeding': 'completed',
                'paused': 'pending',
            }
            
            raw_status = task_info.get('status', '0')
            status = status_map.get(str(raw_status), 'pending')
            
            # Get progress (0-100)
            progress = task_info.get('progress', 0) or task_info.get('percentDone', 0)
            if isinstance(progress, float) and progress <= 1.0:
                progress = int(progress * 100)
            else:
                progress = int(progress)
            
            # Get speed (bytes/sec)
            speed = task_info.get('speed', 0) or task_info.get('rateDownload', 0)
            if speed:
                speed = float(speed)
            
            return {
                'success': True,
                'data': {
                    'status': status,
                    'progress': progress,
                    'speed': speed
                }
            }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'Failed to get task status: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'Failed to get offline task status: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to get task status: {str(e)}'
            }
    
    def get_session_metadata(self) -> Dict[str, Any]:
        """
        Get session metadata (login method, client credentials, etc).
        
        Returns:
            Dict with metadata or empty dict if not found
        """
        try:
            metadata_json = self.secret_store.get_secret('cloud123_session_metadata')
            if metadata_json:
                return json.loads(metadata_json)
        except Exception as e:
            logger.warning(f'Failed to get session metadata: {str(e)}')
        
        return {}
