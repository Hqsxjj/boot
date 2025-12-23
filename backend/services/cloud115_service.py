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

    def set_qps(self, qps: float):
        """Set QPS limit dynamically."""
        if qps > 0:
            self._qps = float(qps)
            logger.info(f'Cloud115Service QPS updated to {self._qps}')
        else:
            logger.warning(f'Invalid QPS value: {qps}, ignoring')

    def _update_qps(self):
        """Update QPS from secret store/config."""
        # This will be updated externally via set_qps
        pass

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
            secret_val = self.secret_store.get_secret(key)
            if secret_val:
                available_keys.append(key)
                # 显示部分内容用于调试
                preview = secret_val[:80] + '...' if len(secret_val) > 80 else secret_val
                logger.info(f'115 凭证 {key}: 长度={len(secret_val)}, 预览={preview}')
        
        logger.info(f'115 凭证检查: 可用密钥 = {available_keys}')
        
        if not available_keys:
            raise ValueError('未找到任何 115 登录凭证，请先登录')
        
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
                    # 尝试解析 JSON
                    try:
                        cookies = json.loads(cookies_json)
                    except json.JSONDecodeError:
                        # 如果不是 JSON，尝试解析为 cookie 字符串格式
                        logger.warning(f'{secret_key} 不是 JSON 格式，尝试解析为 cookie 字符串')
                        cookies = {}
                        for part in cookies_json.replace('\n', ';').split(';'):
                            part = part.strip()
                            if '=' in part:
                                k, v = part.split('=', 1)
                                cookies[k.strip()] = v.strip()
                    
                    # 如果是 token 格式，跳过
                    if 'access_token' in cookies or 'refresh_token' in cookies:
                        logger.debug(f'{secret_key} 是 token 格式，跳过')
                        continue
                    
                    logger.info(f'尝试使用 {source_name} ({secret_key}) 初始化 P115Client，Cookie 键: {list(cookies.keys())}')
                    
                    if not cookies:
                        logger.warning(f'{secret_key} 解析后为空，跳过')
                        continue
                    
                    if hasattr(self.p115client, 'P115Client'):
                        # 尝试创建客户端
                        client = self.p115client.P115Client(cookies=cookies)
                        
                        # 验证客户端可以工作（尝试简单调用）
                        try:
                            # 尝试获取用户信息来验证
                            if hasattr(client, 'user_id'):
                                uid = client.user_id
                                logger.info(f'p115client 已使用 {source_name} 凭证初始化成功，用户ID: {uid}')
                            else:
                                logger.info(f'p115client 已使用 {source_name} 凭证初始化成功（无法验证用户ID）')
                        except Exception as ve:
                            logger.warning(f'{source_name} 初始化后验证失败（继续使用）: {ve}')
                        
                        return client
                except Exception as e:
                    errors.append(f'{source_name}: {e}')
                    logger.warning(f'使用 {source_name} 初始化 p115client 失败: {e}', exc_info=True)
        
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
                    # 关键判断: 目录有 cid 而没有 fid，文件有 fid
                    has_cid = 'cid' in entry and entry.get('cid') is not None
                    has_fid = 'fid' in entry and entry.get('fid') is not None
                    
                    entry_id = entry.get('cid') or entry.get('fid') or entry.get('id') or entry.get('file_id')
                    entry_name = entry.get('n') or entry.get('name')
                    
                    # 多重目录检测:
                    # 1. ico=='folder' (最可靠)
                    # 2. fc=='folder' 
                    # 3. file_type==0
                    # 4. 有 cid 但没有 fid (115 目录特征)
                    # 5. is_directory 直接字段
                    is_directory = (
                        entry.get('ico') == 'folder' or 
                        entry.get('fc') == 'folder' or
                        entry.get('file_type') == 0 or 
                        (has_cid and not has_fid) or
                        entry.get('is_directory')
                    )
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
            
            p115_service = get_p115_service(self.secret_store)
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
            
            p115_service = get_p115_service(self.secret_store)
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
    
    # ==================== OAuth PKCE Methods ====================
    
    def generate_pkce(self) -> Dict[str, str]:
        """
        Generate PKCE code_verifier and code_challenge for OAuth.
        
        Returns:
            Dict with code_verifier and code_challenge
        """
        import secrets
        import hashlib
        import base64
        
        # Generate code_verifier (43-128 characters)
        code_verifier = secrets.token_urlsafe(64)[:128]
        
        # Generate code_challenge (SHA256 hash, base64url encoded)
        code_challenge_digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge_digest).decode('ascii').rstrip('=')
        
        return {
            'code_verifier': code_verifier,
            'code_challenge': code_challenge
        }
    
    def get_oauth_url(self, app_id: str, code_challenge: str, redirect_uri: str = 'http://localhost:8080/callback') -> str:
        """
        Construct OAuth authorization URL for 115 Open Platform.
        
        Args:
            app_id: Third-party App ID
            code_challenge: PKCE code_challenge
            redirect_uri: Redirect URI after authorization
        
        Returns:
            Authorization URL string
        """
        import urllib.parse
        
        # 115 OAuth endpoints
        base_url = 'https://open.115.com/oauth2/authorize'
        
        params = {
            'response_type': 'code',
            'client_id': app_id,
            'redirect_uri': redirect_uri,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'scope': 'user:read+file:read+file:write+offline:read+offline:write'
        }
        
        return f"{base_url}?{urllib.parse.urlencode(params)}"
    
    def exchange_code_for_token(self, app_id: str, app_secret: str, code: str, 
                                 code_verifier: str, redirect_uri: str = 'http://localhost:8080/callback') -> Dict[str, Any]:
        """
        Exchange authorization code for access_token and refresh_token.
        
        Args:
            app_id: Third-party App ID
            app_secret: Third-party App Secret
            code: Authorization code from callback
            code_verifier: PKCE code_verifier
            redirect_uri: Must match the one used in authorization
        
        Returns:
            Dict with success flag and token data
        """
        import requests
        
        try:
            token_url = 'https://passportapi.115.com/open/authApi/accessToken'
            
            payload = {
                'grant_type': 'authorization_code',
                'client_id': app_id,
                'client_secret': app_secret,
                'code': code,
                'code_verifier': code_verifier,
                'redirect_uri': redirect_uri
            }
            
            response = requests.post(token_url, data=payload, timeout=30)
            result = response.json()
            
            if result.get('state') == False or result.get('errno'):
                return {
                    'success': False,
                    'error': result.get('error') or result.get('message') or '获取 token 失败'
                }
            
            # Extract token data
            data = result.get('data', result)
            token_data = {
                'access_token': data.get('access_token'),
                'refresh_token': data.get('refresh_token'),
                'expires_in': data.get('expires_in', 7200),
                'token_type': data.get('token_type', 'Bearer')
            }
            
            # Save tokens to secret store
            self.secret_store.set_secret('cloud115_openapp_cookies', json.dumps(token_data))
            self.secret_store.set_secret('cloud115_session_metadata', json.dumps({
                'login_method': 'oauth_pkce',
                'app_id': app_id,
                'timestamp': datetime.now().isoformat()
            }))
            
            logger.info(f'115 OAuth token 已保存，access_token: {token_data["access_token"][:20]}...')
            
            return {
                'success': True,
                'data': token_data
            }
            
        except Exception as e:
            logger.error(f'交换 token 失败: {str(e)}')
            return {
                'success': False,
                'error': f'交换 token 失败: {str(e)}'
            }
    
    def refresh_access_token(self, refresh_token: str = None) -> Dict[str, Any]:
        """
        Refresh access_token using refresh_token.
        
        Args:
            refresh_token: Optional, if not provided will use stored token
        
        Returns:
            Dict with success flag and new token data
        """
        import requests
        
        try:
            # Get stored token if not provided
            if not refresh_token:
                stored_json = self.secret_store.get_secret('cloud115_openapp_cookies')
                if stored_json:
                    stored_data = json.loads(stored_json)
                    refresh_token = stored_data.get('refresh_token')
            
            if not refresh_token:
                return {
                    'success': False,
                    'error': '没有可用的 refresh_token'
                }
            
            refresh_url = 'https://passportapi.115.com/open/authApi/accessToken'
            
            payload = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token
            }
            
            response = requests.post(refresh_url, data=payload, timeout=30)
            result = response.json()
            
            if result.get('state') == False or result.get('errno'):
                return {
                    'success': False,
                    'error': result.get('error') or result.get('message') or '刷新 token 失败'
                }
            
            # Extract token data
            data = result.get('data', result)
            token_data = {
                'access_token': data.get('access_token'),
                'refresh_token': data.get('refresh_token') or refresh_token,
                'expires_in': data.get('expires_in', 7200),
                'token_type': data.get('token_type', 'Bearer')
            }
            
            # Update stored tokens
            self.secret_store.set_secret('cloud115_openapp_cookies', json.dumps(token_data))
            
            logger.info('115 access_token 已刷新')
            
            return {
                'success': True,
                'data': token_data
            }
            
        except Exception as e:
            logger.error(f'刷新 token 失败: {str(e)}')
            return {
                'success': False,
                'error': f'刷新 token 失败: {str(e)}'
            }
    
    # ==================== Offline Download API ====================
    
    def get_offline_quota(self) -> Dict[str, Any]:
        """获取离线下载配额信息"""
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'offline_quota'):
                result = client.offline_quota()
            elif hasattr(client, 'offline') and hasattr(client.offline, 'quota'):
                result = client.offline.quota()
            else:
                return {'success': False, 'error': '不支持获取离线配额'}
            
            return {
                'success': True,
                'data': result if isinstance(result, dict) else {'quota': result}
            }
        except Exception as e:
            logger.error(f'获取离线配额失败: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    def list_offline_tasks(self, page: int = 1) -> Dict[str, Any]:
        """获取离线下载任务列表"""
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'offline_list'):
                result = client.offline_list({'page': page})
            elif hasattr(client, 'offline') and hasattr(client.offline, 'list'):
                result = client.offline.list(page=page)
            else:
                return {'success': False, 'error': '不支持获取离线任务列表'}
            
            # Format task list
            tasks = []
            task_list = result.get('tasks', result.get('data', [])) if isinstance(result, dict) else result
            for task in task_list:
                if isinstance(task, dict):
                    tasks.append({
                        'id': task.get('info_hash') or task.get('task_id'),
                        'name': task.get('name') or task.get('file_name'),
                        'size': task.get('size', 0),
                        'status': task.get('status'),
                        'progress': task.get('percentDone', 0),
                        'add_time': task.get('add_time')
                    })
            
            return {
                'success': True,
                'data': tasks
            }
        except Exception as e:
            logger.error(f'获取离线任务列表失败: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    def add_offline_url(self, urls: List[str], save_cid: str = '0') -> Dict[str, Any]:
        """添加离线下载链接任务（支持 HTTP/磁力链接）"""
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'offline_add_url'):
                result = client.offline_add_url({'url': urls, 'wp_path_id': save_cid})
            elif hasattr(client, 'offline') and hasattr(client.offline, 'add_url'):
                result = client.offline.add_url(urls, save_cid)
            else:
                return {'success': False, 'error': '不支持添加离线任务'}
            
            return {
                'success': True,
                'data': result if isinstance(result, dict) else {'result': result}
            }
        except Exception as e:
            logger.error(f'添加离线任务失败: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    def delete_offline_task(self, task_ids: List[str]) -> Dict[str, Any]:
        """删除离线下载任务"""
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'offline_del'):
                result = client.offline_del({'hash': task_ids})
            elif hasattr(client, 'offline') and hasattr(client.offline, 'delete'):
                result = client.offline.delete(task_ids)
            else:
                return {'success': False, 'error': '不支持删除离线任务'}
            
            return {
                'success': True,
                'data': result if isinstance(result, dict) else {'deleted': task_ids}
            }
        except Exception as e:
            logger.error(f'删除离线任务失败: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    def clear_offline_tasks(self, flag: int = 0) -> Dict[str, Any]:
        """
        清空离线下载任务
        
        Args:
            flag: 0=清空已完成, 1=清空全部
        """
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'offline_clear'):
                result = client.offline_clear({'flag': flag})
            elif hasattr(client, 'offline') and hasattr(client.offline, 'clear'):
                result = client.offline.clear(flag=flag)
            else:
                return {'success': False, 'error': '不支持清空离线任务'}
            
            return {
                'success': True,
                'data': result if isinstance(result, dict) else {'cleared': True}
            }
        except Exception as e:
            logger.error(f'清空离线任务失败: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    # ==================== Video Playback API ====================
    
    def get_video_play_url(self, file_id: str) -> Dict[str, Any]:
        """获取视频在线播放地址"""
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'fs_video_play'):
                result = client.fs_video_play({'pickcode': file_id})
            elif hasattr(client, 'video_play'):
                result = client.video_play(file_id)
            else:
                return {'success': False, 'error': '不支持获取视频播放地址'}
            
            return {
                'success': True,
                'data': result if isinstance(result, dict) else {'url': result}
            }
        except Exception as e:
            logger.error(f'获取视频播放地址失败: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    def get_video_subtitles(self, file_id: str) -> Dict[str, Any]:
        """获取视频字幕列表"""
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'fs_video_subtitle'):
                result = client.fs_video_subtitle({'pickcode': file_id})
            elif hasattr(client, 'video_subtitle'):
                result = client.video_subtitle(file_id)
            else:
                return {'success': False, 'error': '不支持获取视频字幕'}
            
            subtitles = result.get('list', []) if isinstance(result, dict) else result
            return {
                'success': True,
                'data': subtitles
            }
        except Exception as e:
            logger.error(f'获取视频字幕失败: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    # ==================== File Search API ====================
    
    def search_files(self, keyword: str, cid: str = '0', limit: int = 50) -> Dict[str, Any]:
        """搜索文件"""
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'fs_search'):
                result = client.fs_search({'search_value': keyword, 'cid': int(cid), 'limit': limit})
            elif hasattr(client, 'search'):
                result = client.search(keyword, cid=cid, limit=limit)
            else:
                return {'success': False, 'error': '不支持文件搜索'}
            
            # Format results
            files = []
            file_list = result.get('data', []) if isinstance(result, dict) else result
            for f in file_list:
                if isinstance(f, dict):
                    files.append({
                        'id': str(f.get('fid') or f.get('cid') or f.get('file_id')),
                        'name': f.get('n') or f.get('name'),
                        'size': f.get('s') or f.get('size', 0),
                        'is_directory': f.get('ico') == 'folder'
                    })
            
            return {
                'success': True,
                'data': files
            }
        except Exception as e:
            logger.error(f'搜索文件失败: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    def copy_files(self, file_ids: List[str], target_cid: str) -> Dict[str, Any]:
        """复制文件到指定目录"""
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'fs_copy'):
                result = client.fs_copy({'fid': file_ids, 'pid': int(target_cid)})
            elif hasattr(client, 'copy'):
                result = client.copy(file_ids, target_cid)
            else:
                return {'success': False, 'error': '不支持复制文件'}
            
            return {
                'success': True,
                'data': result if isinstance(result, dict) else {'copied': file_ids}
            }
        except Exception as e:
            logger.error(f'复制文件失败: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    def get_recycle_list(self, page: int = 1, limit: int = 50) -> Dict[str, Any]:
        """获取回收站列表"""
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'recyclebin_list'):
                result = client.recyclebin_list({'offset': (page - 1) * limit, 'limit': limit})
            elif hasattr(client, 'recycle_list'):
                result = client.recycle_list(page=page, limit=limit)
            else:
                return {'success': False, 'error': '不支持获取回收站'}
            
            files = []
            file_list = result.get('data', []) if isinstance(result, dict) else result
            for f in file_list:
                if isinstance(f, dict):
                    files.append({
                        'id': str(f.get('id') or f.get('file_id')),
                        'name': f.get('file_name') or f.get('name'),
                        'delete_time': f.get('dtime') or f.get('delete_time')
                    })
            
            return {
                'success': True,
                'data': files
            }
        except Exception as e:
            logger.error(f'获取回收站失败: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    def restore_recycle(self, file_ids: List[str]) -> Dict[str, Any]:
        """从回收站恢复文件"""
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'recyclebin_revert'):
                result = client.recyclebin_revert({'rid': file_ids})
            elif hasattr(client, 'recycle_revert'):
                result = client.recycle_revert(file_ids)
            else:
                return {'success': False, 'error': '不支持恢复回收站文件'}
            
            return {
                'success': True,
                'data': result if isinstance(result, dict) else {'restored': file_ids}
            }
        except Exception as e:
            logger.error(f'恢复回收站文件失败: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    def clear_recycle(self) -> Dict[str, Any]:
        """清空回收站"""
        try:
            client = self._get_authenticated_client()
            
            if hasattr(client, 'recyclebin_clean'):
                result = client.recyclebin_clean()
            elif hasattr(client, 'recycle_clean'):
                result = client.recycle_clean()
            else:
                return {'success': False, 'error': '不支持清空回收站'}
            
            return {
                'success': True,
                'data': result if isinstance(result, dict) else {'cleared': True}
            }
        except Exception as e:
            logger.error(f'清空回收站失败: {str(e)}')
            return {'success': False, 'error': str(e)}