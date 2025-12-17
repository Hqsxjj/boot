import json
import logging
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from services.secret_store import SecretStore

logger = logging.getLogger(__name__)

# 123 云盘 API 基础配置
CLOUD123_API_BASE = "https://open-api.123pan.com"


class Cloud123Service:
    """Service for interacting with 123 cloud via p123client or REST API."""
    
    def __init__(self, secret_store: SecretStore):
        """
        Initialize Cloud123Service.
        
        Args:
            secret_store: SecretStore instance for retrieving tokens
        """
        self.secret_store = secret_store
        self._access_token = None
        self._token_expires_at = None
        self._client = None
        
        # 尝试导入 p123client
        try:
            from p123client import P123Client
            self.P123Client = P123Client
            logger.info('p123client library loaded successfully')
        except ImportError:
            self.P123Client = None
            logger.warning('p123client not installed, using REST API fallback')
            
        # Rate limiting
        self._last_request_time = 0
        self._qps = 1 # Default QPS
        self._lock = None
        
        try:
            import threading
            self._lock = threading.Lock()
        except ImportError:
            pass

    def _wait_for_rate_limit(self):
        """Enforce QPS limit."""
        import time
        
        # Enforce rate of 1 req/sec by default
        interval = 1.0 / self._qps
        
        if self._lock:
            with self._lock:
                current_time = time.time()
                time_passed = current_time - self._last_request_time
                if time_passed < interval:
                    sleep_time = interval - time_passed
                    time.sleep(sleep_time)
                self._last_request_time = time.time()
        else:
            current_time = time.time()
            time_passed = current_time - self._last_request_time
            if time_passed < interval:
                time.sleep(interval - time_passed)
            self._last_request_time = time.time()
    
    def _get_p123_client(self):
        """Get p123client instance with password or OAuth credentials."""
        # Enforce rate limit
        self._wait_for_rate_limit()
        
        if not self.P123Client:
            return None
        
        if self._client:
            return self._client
        
        # 优先尝试密码登录凭证
        password_creds_json = self.secret_store.get_secret('cloud123_password_credentials')
        if password_creds_json:
            try:
                creds = json.loads(password_creds_json)
                passport = creds.get('passport')  # 手机号或邮箱
                password = creds.get('password')
                
                if passport and password:
                    self._client = self.P123Client(passport=passport, password=password)
                    logger.info('p123client initialized with password credentials')
                    return self._client
            except Exception as e:
                logger.warning(f'Failed to initialize p123client with password: {e}')
                import traceback
                logger.warning(f'Traceback: {traceback.format_exc()}')
        
        # 回退到 OAuth 凭证
        creds_json = self.secret_store.get_secret('cloud123_oauth_credentials')
        if not creds_json:
            logger.warning('No credentials found for p123client')
            return None
        
        try:
            creds = json.loads(creds_json)
            client_id = creds.get('clientId')
            client_secret = creds.get('clientSecret')
            
            if not client_id or not client_secret:
                logger.warning('Missing clientId or clientSecret')
                return None
            
            # 使用 client_id 和 client_secret 创建客户端
            self._client = self.P123Client(client_id=client_id, client_secret=client_secret)
            logger.info('p123client initialized with OAuth credentials')
            return self._client
        except Exception as e:
            logger.error(f'Failed to initialize p123client: {e}')
            return None
    
    def login_with_password(self, passport: str, password: str) -> Dict[str, Any]:
        """
        使用账号密码登录123云盘。
        
        Args:
            passport: 手机号或邮箱
            password: 密码
        
        Returns:
            Dict with success flag
        """
        if not self.P123Client:
            return {
                'success': False,
                'error': 'p123client library not installed'
            }
        
        try:
            # 尝试创建客户端验证凭证
            client = self.P123Client(passport=passport, password=password)
            
            # 验证登录是否成功：调用一个简单的API来验证凭证有效性
            try:
                # 尝试获取用户信息或列出根目录来验证凭证
                if hasattr(client, 'open_fs_file_list'):
                    resp = client.open_fs_file_list({'parentFileId': 0, 'limit': 1, 'Page': 1})
                    if resp.get('code') != 0:
                        return {
                            'success': False,
                            'error': f"凭证验证失败: {resp.get('message', '未知错误')}"
                        }
                elif hasattr(client, 'user_info'):
                    client.user_info()  # 尝试获取用户信息
            except Exception as verify_error:
                logger.warning(f'Credential verification API call failed: {verify_error}')
                return {
                    'success': False,
                    'error': f'账号或密码错误: {str(verify_error)}'
                }
            
            logger.info(f'p123client password login successful for passport: {passport[:3]}***')
            
            # 保存凭证到 SecretStore
            creds = {
                'passport': passport,
                'password': password,
                'login_method': 'password',
                'logged_in_at': datetime.now().isoformat()
            }
            self.secret_store.set_secret('cloud123_password_credentials', json.dumps(creds))
            
            # 更新缓存的客户端
            self._client = client
            
            # 保存会话元数据
            metadata = {
                'login_method': 'password',
                'passport': passport[:3] + '***',
                'logged_in_at': datetime.now().isoformat()
            }
            self.secret_store.set_secret('cloud123_session_metadata', json.dumps(metadata))
            
            return {
                'success': True,
                'data': {
                    'message': '登录成功',
                    'login_method': 'password'
                }
            }
        except Exception as e:
            logger.error(f'Password login failed: {e}')
            return {
                'success': False,
                'error': f'登录失败: {str(e)}'
            }
    
    def _get_access_token(self) -> Optional[str]:
        """
        Get valid access token, refreshing if necessary.
        
        Returns:
            Valid access token or None
        """
        # 检查缓存的 token 是否有效
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at:
                return self._access_token
        
        # 尝试从 secret store 获取保存的 token
        token_json = self.secret_store.get_secret('cloud123_token')
        if token_json:
            try:
                token_data = json.loads(token_json)
                expires_at_str = token_data.get('expires_at')
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if datetime.now() < expires_at:
                        self._access_token = token_data.get('access_token')
                        self._token_expires_at = expires_at
                        return self._access_token
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f'Invalid token data: {e}')
        
        # 需要刷新 token - 获取 OAuth 凭据
        creds_json = self.secret_store.get_secret('cloud123_oauth_credentials')
        if not creds_json:
            logger.warning('No OAuth credentials found')
            return None
        
        try:
            creds = json.loads(creds_json)
            client_id = creds.get('clientId')
            client_secret = creds.get('clientSecret')
            
            if not client_id or not client_secret:
                logger.warning('Missing clientId or clientSecret')
                return None
            
            # 调用 123 云盘 API 获取 access_token
            new_token = self._request_access_token(client_id, client_secret)
            if new_token:
                return new_token
        except json.JSONDecodeError as e:
            logger.error(f'Failed to parse OAuth credentials: {e}')
        
        return None
    
    def _request_access_token(self, client_id: str, client_secret: str) -> Optional[str]:
        """
        Request new access token from 123 cloud API.
        
        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret
        
        Returns:
            Access token or None
        """
        try:
            url = f"{CLOUD123_API_BASE}/api/v1/access_token"
            payload = {
                "clientID": client_id,
                "clientSecret": client_secret
            }
            headers = {
                "Content-Type": "application/json",
                "Platform": "open_platform"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('code') == 0:
                result = data.get('data', {})
                access_token = result.get('accessToken')
                expired_at = result.get('expiredAt')  # 返回的是日期字符串，如 "2026-03-14T01:33:55+08:00"
                
                if access_token:
                    # 缓存 token
                    self._access_token = access_token
                    
                    # 解析过期时间
                    if expired_at and isinstance(expired_at, str):
                        try:
                            # 解析 ISO 格式日期字符串
                            self._token_expires_at = datetime.fromisoformat(expired_at.replace('+08:00', '+08:00').replace('Z', '+00:00'))
                        except ValueError:
                            # 如果解析失败，默认 2 小时后过期
                            self._token_expires_at = datetime.now() + timedelta(hours=2)
                    else:
                        self._token_expires_at = datetime.now() + timedelta(hours=2)
                    
                    # 保存到 secret store
                    token_data = {
                        'access_token': access_token,
                        'expires_at': self._token_expires_at.isoformat()
                    }
                    self.secret_store.set_secret('cloud123_token', json.dumps(token_data))
                    
                    logger.info('Successfully obtained 123 cloud access token')
                    return access_token
            else:
                logger.error(f"Failed to get access token: {data.get('message', 'Unknown error')}")
        except requests.RequestException as e:
            logger.error(f'Failed to request access token: {e}')
        except Exception as e:
            logger.error(f'Unexpected error getting access token: {e}')
        
        return None
    
    def _make_api_request(self, method: str, endpoint: str, params: Dict = None, json_data: Dict = None) -> Dict[str, Any]:
        """
        Make authenticated API request to 123 cloud.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json_data: JSON body data
        
        Returns:
            API response data or error dict
        """
        # Enforce rate limit
        self._wait_for_rate_limit()
        
        access_token = self._get_access_token()
        if not access_token:
            return {
                'success': False,
                'error': 'No valid access token. Please configure OAuth credentials.'
            }
        
        try:
            url = f"{CLOUD123_API_BASE}{endpoint}"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Platform": "open_platform"
            }
            
            if method.upper() == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, json=json_data, headers=headers, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, json=json_data, headers=headers, timeout=30)
            else:
                return {'success': False, 'error': f'Unsupported HTTP method: {method}'}
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0:
                return {
                    'success': True,
                    'data': data.get('data', {})
                }
            else:
                return {
                    'success': False,
                    'error': data.get('message', 'Unknown API error'),
                    'code': data.get('code')
                }
        except requests.RequestException as e:
            logger.error(f'API request failed: {e}')
            return {
                'success': False,
                'error': f'API request failed: {str(e)}'
            }
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }

    def save_share(self, share_code: str, access_code: str = None,
                   save_path: str = '0') -> Dict[str, Any]:
        """
        转存 123 云盘分享链接到指定目录。
        
        Args:
            share_code: 分享码 (如 abc123-xyz)
            access_code: 提取码
            save_path: 保存目录 ID，默认根目录
        
        Returns:
            Dict with success flag and saved file info
        """
        try:
            # 首先获取分享信息
            share_info_payload = {
                'shareKey': share_code,
                'sharePwd': access_code or ''
            }
            
            share_result = self._make_api_request('POST', '/api/v1/share/info', json_data=share_info_payload)
            
            if not share_result.get('success'):
                return {
                    'success': False,
                    'error': share_result.get('error', '无法获取分享信息，可能链接已失效或需要提取码')
                }
            
            share_data = share_result.get('data', {})
            file_list = share_data.get('fileList', []) if isinstance(share_data, dict) else []
            
            if not file_list:
                return {
                    'success': False,
                    'error': '分享中没有文件'
                }
            
            # 获取所有文件 ID
            file_ids = [item.get('fileId') for item in file_list if item.get('fileId')]
            
            if not file_ids:
                return {
                    'success': False,
                    'error': '无法获取分享文件列表'
                }
            
            # 转存文件
            save_payload = {
                'shareKey': share_code,
                'sharePwd': access_code or '',
                'fileIdList': file_ids,
                'parentFileId': int(save_path) if save_path != '0' else 0
            }
            
            save_result = self._make_api_request('POST', '/api/v1/share/file/save', json_data=save_payload)
            
            if save_result.get('success'):
                return {
                    'success': True,
                    'data': {
                        'file_id': file_ids[0] if len(file_ids) == 1 else file_ids,
                        'count': len(file_ids),
                        'save_path': save_path
                    },
                    'message': f'成功转存 {len(file_ids)} 个文件'
                }
            else:
                return {
                    'success': False,
                    'error': save_result.get('error', '转存失败')
                }
                
        except Exception as e:
            logger.error(f'Failed to save 123 share: {str(e)}')
            return {
                'success': False,
                'error': f'转存失败: {str(e)}'
            }
    
    def create_directory(self, parent_id: str, name: str) -> Dict[str, Any]:
        """
        Create a directory on 123 cloud.
        
        Args:
            parent_id: Parent directory ID
            name: Directory name
        
        Returns:
            Dict with success flag and new directory info
        """
        # 123 云盘 API 使用 parentFileId 参数
        # parent_id 为 0 表示根目录
        if parent_id == '/' or parent_id == '':
            parent_id = '0'
            
        # 1. 尝试使用 p123client
        p123_client = self._get_p123_client()
        if p123_client:
            try:
                # p123client mkdir
                resp = p123_client.mkdir({
                    'parentFileId': int(parent_id),
                    'filename': name
                })
                
                if resp.get('code') == 0:
                    data = resp.get('data', {})
                    return {
                        'success': True,
                        'data': {
                            'id': str(data.get('fileId')),
                            'name': name,
                            'parent_id': parent_id
                        }
                    }
                else:
                    logger.warning(f"p123client mkdir failed: {resp.get('message')}, falling back to REST API")
            except Exception as e:
                logger.warning(f"p123client mkdir error: {e}, falling back to REST API")
        
        # 2. 回退到 REST API
        try:
            payload = {
                'parentFileId': int(parent_id),
                'filename': name
            }
            
            result = self._make_api_request('POST', '/api/v1/file/mkdir', json_data=payload)
            
            if result.get('success'):
                data = result.get('data', {})
                return {
                    'success': True,
                    'data': {
                        'id': str(data.get('fileId')),
                        'name': name,
                        'parent_id': parent_id
                    }
                }
            return result
        except Exception as e:
            logger.error(f'Failed to create directory {name} in {parent_id}: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to create directory: {str(e)}'
            }
    
    def list_directory(self, dir_id: str = '0') -> Dict[str, Any]:
        """
        List directory contents from 123 cloud.
        
        Args:
            dir_id: Directory ID, defaults to '0' for root
        
        Returns:
            Dict with success flag and list of entries
        """
        # 123 云盘 API 使用 parentFileId 参数
        # dir_id 为 0 表示根目录
        if dir_id == '/' or dir_id == '':
            dir_id = '0'
        
        # 优先尝试使用 p123client
        p123_client = self._get_p123_client()
        if p123_client:
            try:
                # p123client 使用 open 接口
                resp = p123_client.open_fs_file_list({
                    'parentFileId': int(dir_id),
                    'limit': 100,
                    'Page': 1,
                    'orderBy': 'file_name',
                    'orderDirection': 'asc'
                })
                
                if resp.get('code') == 0:
                    api_data = resp.get('data', {})
                    file_list = api_data.get('fileList', []) if isinstance(api_data, dict) else []
                    
                    entries = []
                    for item in file_list:
                        entry_id = item.get('fileId')
                        entry_name = item.get('filename') or item.get('fileName')
                        is_directory = item.get('type') == 1  # 1 = 文件夹, 0 = 文件
                        update_time = item.get('updateTime', '')
                        
                        if entry_id and entry_name:
                            entries.append({
                                'id': str(entry_id),
                                'name': entry_name,
                                'children': is_directory,
                                'date': update_time[:10] if update_time else datetime.now().strftime('%Y-%m-%d')
                            })
                    
                    return {
                        'success': True,
                        'data': entries
                    }
                else:
                    logger.warning(f"p123client list failed: {resp.get('message')}, falling back to REST API")
            except Exception as e:
                logger.warning(f"p123client list error: {e}, falling back to REST API")
        
        # 回退到 REST API
        try:
            params = {
                'parentFileId': int(dir_id),
                'limit': 100,
                'Page': 1,
                'orderBy': 'file_name',
                'orderDirection': 'asc'
            }
            
            result = self._make_api_request('GET', '/api/v2/file/list', params=params)
            
            if not result.get('success'):
                return result
            
            # 转换数据格式
            api_data = result.get('data', {})
            file_list = api_data.get('fileList', []) if isinstance(api_data, dict) else api_data
            
            entries = []
            for item in file_list:
                entry_id = item.get('fileId')
                entry_name = item.get('filename') or item.get('fileName')
                is_directory = item.get('type') == 1  # 1 = 文件夹, 0 = 文件
                update_time = item.get('updateTime', '')
                
                if entry_id and entry_name:
                    entries.append({
                        'id': str(entry_id),
                        'name': entry_name,
                        'children': is_directory,
                        'date': update_time[:10] if update_time else datetime.now().strftime('%Y-%m-%d')
                    })
            
            return {
                'success': True,
                'data': entries
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
            # 使用单个文件重命名 API
            payload = {
                'fileId': int(file_id),
                'fileName': new_name
            }
            
            result = self._make_api_request('POST', '/api/v1/file/rename', json_data=payload)
            
            if result.get('success'):
                return {
                    'success': True,
                    'data': {
                        'fileId': file_id,
                        'newName': new_name
                    }
                }
            return result
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
            # 使用移动文件 API
            payload = {
                'fileIds': [int(file_id)],
                'toParentFileId': int(target_dir_id)
            }
            
            result = self._make_api_request('POST', '/api/v1/file/move', json_data=payload)
            
            if result.get('success'):
                return {
                    'success': True,
                    'data': {
                        'fileId': file_id,
                        'targetDirId': target_dir_id
                    }
                }
            return result
        except Exception as e:
            logger.error(f'Failed to move file {file_id}: {str(e)}')
            return {
                'success': False,
                'error': f'Failed to move: {str(e)}'
            }
    
    def delete_file(self, file_id: str) -> Dict[str, Any]:
        """
        Delete a file or folder from 123 cloud (move to trash).
        
        Args:
            file_id: File or folder ID
        
        Returns:
            Dict with success flag
        """
        try:
            # 删除文件至回收站 API
            payload = {
                'fileIds': [int(file_id)]
            }
            
            result = self._make_api_request('POST', '/api/v1/file/trash', json_data=payload)
            
            if result.get('success'):
                return {
                    'success': True,
                    'data': {
                        'fileId': file_id
                    }
                }
            return result
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
            # 使用下载 API
            params = {
                'fileId': int(file_id)
            }
            
            result = self._make_api_request('GET', '/api/v1/file/download_info', params=params)
            
            if result.get('success'):
                data = result.get('data', {})
                url = data.get('url') or data.get('downloadUrl')
                return {
                    'success': True,
                    'data': {
                        'fileId': file_id,
                        'url': url
                    }
                }
            return result
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
            # 123 云盘离线下载 API
            payload = {
                'url': source_url,
                'parentFileId': int(save_dir_id) if save_dir_id != '0' else 0
            }
            
            result = self._make_api_request('POST', '/api/v1/offline/download', json_data=payload)
            
            if result.get('success'):
                data = result.get('data', {})
                task_id = data.get('taskId') or data.get('task_id') or data.get('id')
                return {
                    'success': True,
                    'data': {
                        'p123TaskId': str(task_id) if task_id else '',
                        'sourceUrl': source_url,
                        'saveDirId': save_dir_id
                    }
                }
            return result
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
