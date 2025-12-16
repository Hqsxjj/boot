import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from services.secret_store import SecretStore

logger = logging.getLogger(__name__)


class Cloud115Service:
    """Service for interacting with 115 cloud via p115client."""
    
    def __init__(self, secret_store: SecretStore):
        """
        Initialize Cloud115Service.
        
        Args:
            secret_store: SecretStore instance for retrieving cookies
        """
        self.secret_store = secret_store
        self._client = None
        
        try:
            import p115client
            self.p115client = p115client
        except ImportError:
            self.p115client = None
            logger.warning('p115client not installed, 115 operations will be mocked')
            
        # Rate limiting
        self._last_request_time = 0
        self._qps = 1 # Default QPS
        self._lock = None
        
        try:
            import threading
            self._lock = threading.Lock()
        except ImportError:
            pass

    def _update_qps(self):
        """Update QPS from secret store/config."""
        try:
            # Try to get from config store if available, or use default
            # For now we default to 2 requests per second (0.5s interval)
            # You can make this configurable via secret_store if needed
            self._qps = 2.0 
        except Exception as e:
            logger.debug(f'Failed to update QPS from config: {e}')

    def _wait_for_rate_limit(self):
        """Enforce QPS limit."""
        import time
        
        if self._lock:
            with self._lock:
                current_time = time.time()
                # Calculate minimum interval between requests
                interval = 1.0 / self._qps
                
                # If time since last request is less than interval, sleep
                time_passed = current_time - self._last_request_time
                if time_passed < interval:
                    sleep_time = interval - time_passed
                    time.sleep(sleep_time)
                
                self._last_request_time = time.time()
        else:
             # Fallback without lock
            import time
            current_time = time.time()
            interval = 1.0 / self._qps
            time_passed = current_time - self._last_request_time
            if time_passed < interval:
                time.sleep(interval - time_passed)
            self._last_request_time = time.time()

    def _get_authenticated_client(self):
        """Get or create an authenticated p115client instance."""
        # Enforce rate limit before getting client/making requests
        self._wait_for_rate_limit()
        
        if not self.p115client:
            raise ImportError('p115client not installed')
        
        # Get cookies from secret store
        cookies_json = self.secret_store.get_secret('cloud115_cookies')
        if not cookies_json:
            raise ValueError('No 115 cookies found in secret store')
        
        try:
            cookies = json.loads(cookies_json)
        except json.JSONDecodeError:
            raise ValueError('Invalid cookies format in secret store')
        
        # Create client
        if hasattr(self.p115client, 'P115Client'):
            client = self.p115client.P115Client(cookies=cookies)
            return client
        else:
            raise ImportError('p115client.P115Client not available')
    
    def create_directory(self, parent_cid: str, name: str) -> Dict[str, Any]:
        """
        Create a directory on 115 cloud.
        
        Args:
            parent_cid: Parent directory CID
            name: Directory name
        
        Returns:
            Dict with success flag and new directory info
        """
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'fs') and hasattr(client.fs, 'mkdir'):
                # client.fs.mkdir returns the new cid or raises error
                cid = client.fs.mkdir(parent_cid, name)
                if isinstance(cid, dict):
                     # handle case where it returns dict
                     cid = cid.get('id') or cid.get('cid')
                
                return {
                    'success': True,
                    'data': {
                        'id': str(cid),
                        'name': name,
                        'parent_cid': parent_cid
                    }
                }
            elif hasattr(client, 'mkdir'):
                cid = client.mkdir(parent_cid, name)
                return {
                    'success': True,
                    'data': {
                        'id': str(cid),
                        'name': name,
                        'parent_cid': parent_cid
                    }
                }
            else:
                 return {
                    'success': False,
                    'error': 'Create directory operation not supported'
                }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'Failed to create directory: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'Failed to create directory {name} in {parent_cid}: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to create directory: {str(e)}'
            }
    
    def list_directory(self, cid: str = '0') -> Dict[str, Any]:
        """
        List directory contents from 115 cloud.
        
        Args:
            cid: Directory ID (CID), defaults to '0' for root
        
        Returns:
            Dict with success flag and list of entries
        """
        try:
            client = self._get_authenticated_client()
            
            # Get directory listing
            if hasattr(client, 'fs'):
                # Use file system interface
                entries = client.fs.listdir(cid)
            elif hasattr(client, 'list_files'):
                entries = client.list_files(cid)
            else:
                # Fallback: return empty list if method not available
                return {
                    'success': True,
                    'data': []
                }
            
            # Transform entries to match frontend format
            result = []
            for entry in entries:
                # Extract fields with various possible attribute names (Support both dict and object)
                if isinstance(entry, dict):
                    entry_id = entry.get('id') or entry.get('fid') or entry.get('cid') or entry.get('file_id')
                    entry_name = entry.get('name') or entry.get('n')
                    # Check for directory: p115 usually uses 'ico'='folder' or explicit is_directory
                    is_directory = entry.get('is_directory') or entry.get('ico') == 'folder' or entry.get('file_type') == 0
                    timestamp = entry.get('timestamp') or entry.get('t') or entry.get('time')
                else:
                    entry_id = getattr(entry, 'id', None) or getattr(entry, 'fid', None) or getattr(entry, 'cid', None)
                    entry_name = getattr(entry, 'name', None) or getattr(entry, 'n', None)
                    is_directory = getattr(entry, 'is_directory', None) or getattr(entry, 'ico', None) == 'folder'
                    timestamp = getattr(entry, 'timestamp', None) or getattr(entry, 't', None)
                
                # Get timestamp
                if timestamp:
                    try:
                        if isinstance(timestamp, (int, float)):
                            date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                        else:
                            date_str = str(timestamp)[:10]
                    except Exception:
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
            logger.error(f'Failed to list directory {cid}: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to list directory: {str(e)}'
            }
    
    def rename_file(self, file_id: str, new_name: str) -> Dict[str, Any]:
        """
        Rename a file or folder on 115 cloud.
        
        Args:
            file_id: File or folder ID
            new_name: New name
        
        Returns:
            Dict with success flag
        """
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'fs') and hasattr(client.fs, 'rename'):
                client.fs.rename(file_id, new_name)
            elif hasattr(client, 'rename'):
                client.rename(file_id, new_name)
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
    
    def move_file(self, file_id: str, target_cid: str) -> Dict[str, Any]:
        """
        Move a file or folder to another directory on 115 cloud.
        
        Args:
            file_id: File or folder ID
            target_cid: Target directory CID
        
        Returns:
            Dict with success flag
        """
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'fs') and hasattr(client.fs, 'move'):
                client.fs.move(file_id, target_cid)
            elif hasattr(client, 'move'):
                client.move(file_id, target_cid)
            else:
                return {
                    'success': False,
                    'error': 'Move operation not supported'
                }
            
            return {
                'success': True,
                'data': {
                    'fileId': file_id,
                    'targetCid': target_cid
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
        Delete a file or folder from 115 cloud.
        
        Args:
            file_id: File or folder ID
        
        Returns:
            Dict with success flag
        """
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'fs') and hasattr(client.fs, 'delete'):
                client.fs.delete(file_id)
            elif hasattr(client, 'delete'):
                client.delete(file_id)
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
            
            if hasattr(client, 'fs') and hasattr(client.fs, 'get_url'):
                url = client.fs.get_url(file_id)
            elif hasattr(client, 'get_download_url'):
                url = client.get_download_url(file_id)
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
    
    def save_share(self, share_code: str, access_code: str = None, 
                   save_cid: str = '0') -> Dict[str, Any]:
        """
        转存 115 分享链接到指定目录。
        
        Args:
            share_code: 分享码 (如 sw3xxxx)
            access_code: 访问码/提取码
            save_cid: 保存目录 CID，默认根目录
        
        Returns:
            Dict with success flag and saved file info
        """
        try:
            from p115_bridge import get_p115_service
            
            # 获取 cookies
            cookies_json = self.secret_store.get_secret('cloud115_cookies')
            if not cookies_json:
                return {
                    'success': False,
                    'error': '未登录 115 账号，请先登录'
                }
            
            p115_service = get_p115_service()
            result = p115_service.save_share(
                share_code=share_code,
                access_code=access_code,
                save_cid=save_cid,
                cookies=cookies_json
            )
            
            return result
            
        except Exception as e:
            logger.error(f'Failed to save share: {str(e)}')
            return {
                'success': False,
                'error': f'转存失败: {str(e)}'
            }
    
    def create_offline_task(self, source_url: str, save_cid: str) -> Dict[str, Any]:
        """
        Create an offline download task on 115 cloud.
        
        Args:
            source_url: URL or magnet link to download
            save_cid: Target folder CID
        
        Returns:
            Dict with success flag and task ID from 115
        """
        try:
            client = self._get_authenticated_client()
            
            # Try various possible method names
            if hasattr(client, 'offline') and hasattr(client.offline, 'add_url'):
                result = client.offline.add_url(source_url, save_cid)
            elif hasattr(client, 'add_offline_task'):
                result = client.add_offline_task(source_url, save_cid)
            elif hasattr(client, 'offline_add'):
                result = client.offline_add(source_url, save_cid)
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
                    'p115TaskId': task_id,
                    'sourceUrl': source_url,
                    'saveCid': save_cid
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
        Get status of an offline task from 115 cloud.
        
        Args:
            task_id: Task ID from 115
        
        Returns:
            Dict with task status, progress, and speed
        """
        try:
            client = self._get_authenticated_client()
            
            # Try various possible method names
            if hasattr(client, 'offline') and hasattr(client.offline, 'list'):
                tasks = client.offline.list()
            elif hasattr(client, 'list_offline_tasks'):
                tasks = client.list_offline_tasks()
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
        Get session metadata (login method, etc).
        
        Returns:
            Dict with metadata or empty dict if not found
        """
        try:
            metadata_json = self.secret_store.get_secret('cloud115_session_metadata')
            if metadata_json:
                return json.loads(metadata_json)
        except Exception as e:
            logger.warning(f'Failed to get session metadata: {str(e)}')
        
        return {}