import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from services.secret_store import SecretStore
from utils.logger import TaskLogger

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
            logger.warning('未安装 p115client，115 操作将使用模拟模式')
            
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
            logger.debug(f'从配置更新 QPS 失败: {e}')

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
        """Get or create an authenticated p115client instance with fallback between credentials."""
        # Enforce rate limit before getting client/making requests
        self._wait_for_rate_limit()
        
        if not self.p115client:
            raise ImportError('未安装 p115client')
        
        errors = []
        
        # 调试：列出所有可用的凭证
        available_keys = []
        for key in ['cloud115_openapp_cookies', 'cloud115_qr_cookies', 'cloud115_manual_cookies', 'cloud115_cookies']:
            if self.secret_store.get_secret(key):
                available_keys.append(key)
        logger.info(f'115 凭证检查: 可用密钥 = {available_keys}')
        
        # 首先尝试 open_app 模式 (P115OpenClient with access_token)
        open_app_json = self.secret_store.get_secret('cloud115_openapp_cookies')
        if open_app_json:
            try:
                token_data = json.loads(open_app_json)
                # 检查是否是 access_token 格式
                if 'access_token' in token_data or 'refresh_token' in token_data:
                    logger.info('检测到 access_token 格式，尝试使用 P115OpenClient')
                    if hasattr(self.p115client, 'P115OpenClient'):
                        refresh_token = token_data.get('refresh_token', '')
                        access_token = token_data.get('access_token', '')
                        
                        if refresh_token:
                            client = self.p115client.P115OpenClient(refresh_token)
                            logger.info('p115client.P115OpenClient 已使用 refresh_token 初始化')
                            return client
                        elif access_token:
                            client = self.p115client.P115OpenClient.__new__(self.p115client.P115OpenClient)
                            client._access_token = access_token
                            logger.info('p115client.P115OpenClient 已使用 access_token 初始化')
                            return client
                    else:
                        logger.warning('p115client 不支持 P115OpenClient，尝试 Cookie 登录')
            except Exception as e:
                errors.append(f'第三方AppID: {e}')
                logger.warning(f'使用 P115OpenClient 初始化失败: {e}')
        
        # 回退到 Cookie 模式 (P115Client)
        credential_sources = [
            ('cloud115_qr_cookies', 'QR扫码'),
            ('cloud115_manual_cookies', '手动导入'),
            ('cloud115_cookies', '通用'),
        ]
        
        for secret_key, source_name in credential_sources:
            cookies_json = self.secret_store.get_secret(secret_key)
            if cookies_json:
                try:
                    cookies = json.loads(cookies_json)
                    # 如果是 token 格式，跳过
                    if 'access_token' in cookies or 'refresh_token' in cookies:
                        logger.debug(f'{secret_key} 是 token 格式，跳过')
                        continue
                    
                    logger.info(f'尝试使用 {source_name} ({secret_key}) 初始化 P115Client，Cookie 键: {list(cookies.keys())}')
                    
                    if hasattr(self.p115client, 'P115Client'):
                        client = self.p115client.P115Client(cookies=cookies)
                        logger.info(f'p115client 已使用 {source_name} 凭证初始化成功')
                        return client
                except Exception as e:
                    errors.append(f'{source_name}: {e}')
                    logger.warning(f'使用 {source_name} 初始化 p115client 失败: {e}')
        
        if errors:
            error_msg = f'所有 115 登录方式均失败: {errors}'
            logger.error(error_msg)
            raise ValueError(error_msg)
        else:
            error_msg = '在密钥库中未找到 115 cookies'
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def create_directory(self, parent_cid: str, name: str) -> Dict[str, Any]:
        """
        Create a directory on 115 cloud.
        
        Args:
            parent_cid: Parent directory CID
            name: Directory name
        
        Returns:
            Dict with success flag and new directory info
        """
        task_log = TaskLogger('115网盘')
        task_log.start(f'创建目录: {name}')
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
                     'error': '不支持创建目录操作'
                }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'创建目录失败: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            task_log.failure(str(e))
            return {
                'success': False,
                'error': f'创建目录失败: {str(e)}'
            }
    
    def list_directory(self, cid: str = '0') -> Dict[str, Any]:
        """
        List directory contents from 115 cloud.
        
        Args:
            cid: Directory ID (CID), defaults to '0' for root
        
        Returns:
            Dict with success flag and list of entries
        """
        task_log = TaskLogger('115网盘')
        task_log.start(f'浏览目录: CID={cid}')
        try:
            client = self._get_authenticated_client()
            
            # 使用正确的 p115client API: fs_files
            # 参考: https://p115client.readthedocs.io/
            try:
                # p115client 使用 fs_files 方法获取目录内容
                # show_dir=1 表示同时显示目录
                response = client.fs_files({"cid": int(cid), "show_dir": 1, "limit": 100})
                
                # 检查响应格式
                if isinstance(response, dict):
                    if response.get('state', True) == False:
                        error_msg = response.get('error', '获取目录失败')
                        logger.warning(f'fs_files 返回错误: {error_msg}')
                        return {
                            'success': False,
                            'error': error_msg
                        }
                    # 提取文件列表 - p115client 返回格式: {'data': [...], 'count': N, ...}
                    entries = response.get('data', [])
                else:
                    entries = list(response) if response else []
            except AttributeError:
                # 如果 fs_files 不存在，尝试其他方法
                logger.warning('fs_files 方法不存在，尝试备用方案')
                if hasattr(client, 'fs') and hasattr(client.fs, 'listdir'):
                    entries = client.fs.listdir(cid)
                elif hasattr(client, 'list_files'):
                    entries = client.list_files(cid)
                else:
                    return {
                        'success': True,
                        'data': []
                    }
            
            # Transform entries to match frontend format
            result = []
            for entry in entries:
                # Extract fields with various possible attribute names (Support both dict and object)
                if isinstance(entry, dict):
                    # p115client fs_files 返回字段: fid/cid, n/name, ico, t/te
                    entry_id = entry.get('cid') or entry.get('fid') or entry.get('id') or entry.get('file_id')
                    entry_name = entry.get('n') or entry.get('name')
                    # Check for directory: p115 uses 'ico'='folder' or file_type判断
                    is_directory = entry.get('ico') == 'folder' or entry.get('file_type') == 0 or entry.get('is_directory')
                    timestamp = entry.get('te') or entry.get('t') or entry.get('timestamp') or entry.get('time')
                else:
                    entry_id = getattr(entry, 'cid', None) or getattr(entry, 'fid', None) or getattr(entry, 'id', None)
                    entry_name = getattr(entry, 'n', None) or getattr(entry, 'name', None)
                    is_directory = getattr(entry, 'ico', None) == 'folder' or getattr(entry, 'is_directory', None)
                    timestamp = getattr(entry, 'te', None) or getattr(entry, 't', None) or getattr(entry, 'timestamp', None)
                
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
            
            task_log.success(f'获取到 {len(result)} 个项目')
            return {
                'success': True,
                'data': result
            }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'列出目录失败: {str(e)}')
            task_log.failure(str(e))
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'列出目录 {cid} 失败: {str(e)}')
            task_log.failure(str(e))
            return {
                'success': False,
                'error': f'列出目录失败: {str(e)}'
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
                    'error': '不支持重命名操作'
                }
            
            return {
                'success': True,
                'data': {
                    'fileId': file_id,
                    'newName': new_name
                }
            }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'重命名文件失败: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'重命名文件 {file_id} 失败: {str(e)}')
            return {
                'success': False,
                'error': f'重命名失败: {str(e)}'
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
                    'error': '不支持移动操作'
                }
            
            return {
                'success': True,
                'data': {
                    'fileId': file_id,
                    'targetCid': target_cid
                }
            }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'移动文件失败: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'移动文件 {file_id} 失败: {str(e)}')
            return {
                'success': False,
                'error': f'移动失败: {str(e)}'
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
                    'error': '不支持删除操作'
                }
            
            return {
                'success': True,
                'data': {
                    'fileId': file_id
                }
            }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'删除文件失败: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'删除文件 {file_id} 失败: {str(e)}')
            return {
                'success': False,
                'error': f'删除失败: {str(e)}'
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
                    'error': '不支持获取下载链接操作'
                }
            
            return {
                'success': True,
                'data': {
                    'fileId': file_id,
                    'url': url
                }
            }
        
        except (ImportError, ValueError) as e:
            logger.warning(f'获取下载链接失败: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'获取文件 {file_id} 的下载链接失败: {str(e)}')
            return {
                'success': False,
                'error': f'获取下载链接失败: {str(e)}'
            }
    
    def save_share(self, share_code: str, access_code: str = None, 
                   save_cid: str = '0', file_ids: List[str] = None) -> Dict[str, Any]:
        """
        转存 115 分享链接到指定目录。
        
        Args:
            share_code: 分享码 (如 sw3xxxx)
            access_code: 访问码/提取码
            save_cid: 保存目录 CID，默认根目录
            file_ids: 可选的文件 ID 列表，如果提供则只转存这些文件
        
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
                cookies=cookies_json,
                file_ids=file_ids
            )
            
            return result
            
        except Exception as e:
            logger.error(f'转存分享失败: {str(e)}')
            return {
                'success': False,
                'error': f'转存失败: {str(e)}'
            }
    
    def get_share_files(self, share_code: str, access_code: str = None, cid: str = '0') -> Dict[str, Any]:
        """
        获取分享链接中的文件列表
        
        Args:
            share_code: 分享码
            access_code: 提取码
            cid: 子目录 ID，默认为 '0' 表示根目录
        """
        try:
            from p115_bridge import get_p115_service
            
            # 获取 cookies
            cookies_json = self.secret_store.get_secret('cloud115_cookies')
            if not cookies_json:
                return {
                    'success': False,
                    'error': '未登录 115 账号'
                }
            
            p115_service = get_p115_service()
            result = p115_service.get_share_files(
                share_code=share_code,
                access_code=access_code,
                cookies=cookies_json,
                cid=cid
            )
            return result
        except Exception as e:
            logger.error(f'获取分享文件列表失败: {str(e)}')
            return {
                'success': False,
                'error': str(e)
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
                    'error': '不支持创建离线任务操作'
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
            logger.warning(f'创建离线任务失败: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'创建离线任务失败: {str(e)}')
            return {
                'success': False,
                'error': f'创建离线任务失败: {str(e)}'
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
                    'error': '不支持获取离线任务状态操作'
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
                    'error': f'未找到任务 {task_id}'
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
            logger.warning(f'获取任务状态失败: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f'获取离线任务状态失败: {str(e)}')
            return {
                'success': False,
                'error': f'获取任务状态失败: {str(e)}'
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
            logger.warning(f'获取会话元数据失败: {str(e)}')
        
        return {}