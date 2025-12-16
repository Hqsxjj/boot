import os
import json
import uuid
import logging
import base64
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 添加到 p115_bridge.py（靠近其它 device profile 定义处）
ALL_DEVICE_PROFILES_FULL = {
    "web": 8,
    "pcweb": 7,
    "android": 13,
    "android_tv": 14,
    "ios": 9,
    "ipad": 10,
    "applet": 22,
    "mini": 18,
    "qandroid": 17,
    "desktop": 11,
    "windows": 19,
    "mac": 20,
    "linux": 21,
    "harmony": 23,
    "xiaomi": 24,
    "huawei": 25,
    "oppo": 26,
    "vivo": 27,
    "samsung": 28,
    "browser": 29,
    "client": 30,
    "open_app": 31
}

# 22 device profiles for cloud115.loginApp (simplified mapping)
ALL_DEVICE_PROFILES = {
    'web': 8,
    'ios': 9,
    'android': 13,
    'tv': 14,
    'qandroid': 17,
    'mini': 18,
    'windows': 19,
    'mac': 20,
    'linux': 21,
    'applet': 22,
}


class P115Service:
    """Service wrapper around p115client for 115 login functionality."""
    
    def __init__(self):
        """Initialize P115Service."""
        self._client = None
        self._session_cache = {}  # In-memory cache for login sessions
        self._session_timeout = timedelta(minutes=5)  # QR code timeout
        
        # Try to import p115client
        try:
            import p115client
            self.p115client = p115client
        except ImportError:
            self.p115client = None
    
    def _get_p115client_module(self):
        """Get p115client module or raise error."""
        if self.p115client is None:
            raise ImportError('p115client not installed')
        return self.p115client
    
    def _fetch_qrcode_as_base64(self, qrcode_url: str, uid: str = '') -> str:
        """
        下载二维码图片并转换为 base64 data URI。
        如果下载失败，则使用本地 qrcode 库生成。
        
        Args:
            qrcode_url: 二维码图片URL
            uid: 用于本地生成二维码的UID
        
        Returns:
            base64 data URI 格式的图片数据
        """
        logger.info(f"Attempting to fetch QR code from: {qrcode_url}")
        
        # 方案1: 尝试从115 API下载
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://115.com/',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
            }
            
            response = requests.get(qrcode_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 检查响应内容是否是有效的图片
            content_type = response.headers.get('Content-Type', '')
            if 'image' in content_type and len(response.content) > 100:
                img_base64 = base64.b64encode(response.content).decode('utf-8')
                data_uri = f"data:{content_type};base64,{img_base64}"
                logger.info(f"QR code fetched successfully from 115 API, size: {len(response.content)} bytes")
                return data_uri
            else:
                logger.warning(f"Invalid image response from 115 API: content_type={content_type}, size={len(response.content)}")
                
        except Exception as e:
            logger.warning(f"Failed to fetch QR code from 115 API: {str(e)}")
        
        # 方案2: 使用本地 qrcode 库生成
        if uid:
            try:
                import qrcode
                from io import BytesIO
                
                # 115扫码登录的URL格式
                qr_content = f"https://qrcodeapi.115.com/api/1.0/web/1.0/token?uid={uid}"
                
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(qr_content)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                
                img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
                data_uri = f"data:image/png;base64,{img_base64}"
                
                logger.info(f"QR code generated locally using qrcode library for uid: {uid[:8]}...")
                return data_uri
                
            except ImportError:
                logger.error("qrcode library not installed, falling back to third-party service")
            except Exception as e:
                logger.error(f"Failed to generate QR code locally: {str(e)}")
        
        # 方案3: 使用第三方二维码生成服务
        if uid:
            fallback_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https://qrcodeapi.115.com/api/1.0/web/1.0/token?uid={uid}"
            logger.info(f"Using third-party QR service: {fallback_url}")
            return fallback_url
        
        # 最后返回原始URL
        return qrcode_url
    
    def start_qr_login(self, 
                      login_app: str = 'web',
                      login_method: str = 'qrcode',
                      app_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Start a QR code login session.
        
        Args:
            login_app: Device profile (web, ios, android, etc.)
            login_method: 'qrcode', 'cookie', or 'open_app'
            app_id: Third-party App ID (required for open_app method)
        
        Returns:
            Dict with sessionId and qrcode URL
        """
        try:
            p115client = self._get_p115client_module()
            
            session_id = str(uuid.uuid4())
            
            # 区分两种登录逻辑
            if login_method == 'open_app':
                # 第三方应用模式：使用 login_qrcode_token_open
                if not app_id:
                    return {
                        'error': 'App ID is required for open_app login method',
                        'success': False
                    }
                
                actual_app_id = int(app_id) if isinstance(app_id, str) and app_id.isdigit() else app_id
                if isinstance(actual_app_id, str):
                    # app_id 应该是数字，如果仍是字符串则无效
                    return {
                        'error': f'Invalid app_id: {app_id}. Must be a numeric ID.',
                        'success': False
                    }
                logger.info(f"open_app mode: app_id={app_id}, actual_app_id={actual_app_id}, type={type(actual_app_id)}")
                
                # 使用 login_qrcode_token_open 获取第三方应用二维码
                try:
                    qr_token_result = p115client.P115Client.login_qrcode_token_open(actual_app_id)
                    logger.info(f"open_app qr_token_result: state={qr_token_result.get('state')}, code={qr_token_result.get('code')}")
                except Exception as e:
                    logger.error(f"login_qrcode_token_open exception: {str(e)}")
                    raise
                
                if qr_token_result.get('state') != 1:
                    return {
                        'error': f"Failed to get QR token: {qr_token_result.get('message', qr_token_result.get('error', 'Unknown error'))}",
                        'success': False
                    }
                
                qr_data = qr_token_result.get('data', {})
                qrcode_url = qr_data.get('qrcode', '')
                
                # 如果返回数据包含 uid，也存储它
                uid = qr_data.get('uid', '')
                
                # Cache session info - open_app 模式
                self._session_cache[session_id] = {
                    'uid': uid,
                    'qr_data': qr_data,
                    'login_method': 'open_app',
                    'login_app': 'open_app',
                    'app_id': actual_app_id,
                    'started_at': datetime.now(),
                    'status': 'pending'
                }
                
                # 代理下载二维码并转 base64（传递uid用于本地生成备选）
                qrcode_base64 = self._fetch_qrcode_as_base64(qrcode_url, uid) if qrcode_url else ''
                
                return {
                    'sessionId': session_id,
                    'qrcode': qrcode_base64,
                    'login_method': 'open_app',
                    'login_app': 'open_app'
                }
            else:
                # 普通扫码模式：使用 login_qrcode_token
                # p115client.login_qrcode_token 支持 app 参数 (string)
                # Frontend passes 'web', 'ios', 'android', etc. which p115client recognizes
                
                logger.info(f"Starting QR login: login_app={login_app}, login_method={login_method}")
                
                try:
                    # Pass the app parameter
                    qr_token_result = p115client.P115Client.login_qrcode_token(app=login_app)
                except TypeError:
                    # Fallback if p115client version doesn't support 'app' param
                    logger.warning("p115client.login_qrcode_token does not support 'app' param, using default")
                    qr_token_result = p115client.P115Client.login_qrcode_token()
                
                logger.debug(f"QR token result: {qr_token_result}")
                
                if qr_token_result.get('state') != 1:
                    error_msg = qr_token_result.get('message') or qr_token_result.get('error') or 'Unknown error'
                    logger.error(f"Failed to get QR token: {error_msg}")
                    return {
                        'error': f"Failed to get QR token: {error_msg}",
                        'success': False
                    }
                
                qr_data = qr_token_result.get('data', {})
                uid = qr_data.get('uid', '')
                
                if not uid:
                    logger.error(f"No UID in QR token response: {qr_data}")
                    return {
                        'error': 'No UID returned from 115 API',
                        'success': False
                    }
                
                # 新版 p115client 可能直接返回 image data 或 url
                # 如有 qrcode 字段且包含 http，则直接使用
                # 否则构造 qrcodeapi
                if qr_data.get('qrcode') and str(qr_data.get('qrcode')).startswith('http'):
                    qrcode_url = qr_data.get('qrcode')
                else:
                    qrcode_url = f"https://qrcodeapi.115.com/api/1.0/web/1.0/qrcode?uid={uid}"
                
                logger.info(f"QR code generated successfully: uid={uid[:8]}...")
                
                # Cache session info - 普通扫码模式
                self._session_cache[session_id] = {
                    'uid': uid,
                    'qr_data': qr_data,
                    'login_method': login_method,
                    'login_app': login_app,
                    'app_id': app_id,  # 可能为 None，普通模式不需要
                    'started_at': datetime.now(),
                    'status': 'pending'
                }
                
                # 代理下载二维码并转 base64（传递uid用于本地生成备选）
                qrcode_base64 = self._fetch_qrcode_as_base64(qrcode_url, uid)
                
                return {
                    'sessionId': session_id,
                    'qrcode': qrcode_base64,
                    'login_method': login_method,
                    'login_app': login_app
                }
        except ImportError as e:
            logger.error(f"p115client not installed: {str(e)}")
            return {
                'error': 'p115client library not installed',
                'success': False
            }
        except Exception as e:
            logger.exception(f"Failed to start QR login: {str(e)}")
            return {
                'error': f'Failed to start QR login: {str(e)}',
                'success': False
            }
    
    def poll_login_status(self, session_id: str) -> Dict[str, Any]:
        """
        Poll QR code login status.
        
        Args:
            session_id: Session ID from start_qr_login
        
        Returns:
            Dict with status and cookies if successful
        """
        try:
            p115client = self._get_p115client_module()
            session_info = self._session_cache.get(session_id)
            
            if not session_info:
                return {
                    'error': 'Session not found',
                    'success': False
                }
            
            # Check timeout
            if datetime.now() - session_info['started_at'] > self._session_timeout:
                del self._session_cache[session_id]
                return {
                    'error': 'QR code expired',
                    'success': False,
                    'status': 'expired'
                }
            
            qr_data = session_info.get('qr_data', {})
            uid = qr_data.get('uid', '')
            time_val = qr_data.get('time', 0)
            sign = qr_data.get('sign', '')
            
            # 使用 login_qrcode_scan_status 检查扫码状态
            # 构建 payload
            payload = {
                'uid': uid,
                'time': time_val,
                'sign': sign
            }
            
            try:
                status_result = p115client.P115Client.login_qrcode_scan_status(payload)
                
                # 状态码含义:
                # 0: 未扫描
                # 1: 已扫描，等待确认
                # 2: 已确认登录
                # -1/-2: 二维码过期/已取消
                
                status_code = status_result.get('data', {}).get('status', 0)
                
                if status_code == 0:
                    return {
                        'status': 'waiting',
                        'success': True
                    }
                elif status_code == 1:
                    return {
                        'status': 'scanned',
                        'success': True
                    }
                elif status_code == 2:
                    # 用户已确认，获取 cookies
                    try:
                        scan_result = p115client.P115Client.login_qrcode_scan(payload)
                        
                        if scan_result.get('state') == 1:
                            cookie_data = scan_result.get('data', {}).get('cookie', {})
                            
                            # 解析 cookies - 可能是字符串格式或字典格式
                            if isinstance(cookie_data, str):
                                # 解析 cookie 字符串
                                cookies = {}
                                for part in cookie_data.split(';'):
                                    part = part.strip()
                                    if '=' in part:
                                        key, value = part.split('=', 1)
                                        cookies[key.strip()] = value.strip()
                            elif isinstance(cookie_data, dict):
                                cookies = cookie_data
                            else:
                                cookies = {}
                            
                            session_info['status'] = 'success'
                            session_info['cookies'] = cookies
                            
                            return {
                                'status': 'success',
                                'cookies': cookies,
                                'success': True
                            }
                        else:
                            return {
                                'status': 'error',
                                'error': scan_result.get('message', 'Login failed'),
                                'success': False
                            }
                    except Exception as e:
                        return {
                            'status': 'error',
                            'error': f'Failed to complete login: {str(e)}',
                            'success': False
                        }
                else:
                    # 过期或取消
                    session_info['status'] = 'expired'
                    return {
                        'status': 'expired',
                        'success': False
                    }
            except Exception as e:
                # API 调用失败，记录错误并返回错误状态而非假装等待
                logger.warning(f'QR scan status API call failed: {str(e)}')
                return {
                    'status': 'error',
                    'error': f'扫码状态查询失败: {str(e)}',
                    'success': False
                }
        except Exception as e:
            return {
                'error': f'Failed to poll status: {str(e)}',
                'success': False
            }
    
    def validate_cookies(self, cookies: Dict[str, str]) -> bool:
        """
        Validate 115 cookies by attempting to authenticate.
        
        Args:
            cookies: Dictionary of cookies
        
        Returns:
            True if valid, False otherwise
        """
        try:
            if not cookies:
                return False
            
            p115client = self._get_p115client_module()
            
            # Create client with cookies and test authentication
            if hasattr(p115client, 'P115Client'):
                client = p115client.P115Client(cookies=cookies)
            else:
                return False
            
            # Test by getting user info
            if hasattr(client, 'get_user_id'):
                user_id = client.get_user_id()
                return user_id is not None
            elif hasattr(client, 'user_id'):
                return client.user_id is not None
            else:
                # 无法验证时尝试调用一个简单的 API 来确认
                try:
                    if hasattr(client, 'fs') and hasattr(client.fs, 'listdir'):
                        client.fs.listdir('0')  # 尝试列出根目录
                        return True
                except Exception:
                    pass
                # 无法验证，返回 False 而非盲目假设有效
                logger.warning('Unable to validate cookies: no validation method available')
                return False
        except Exception:
            return False
    
    def get_authenticated_client(self, cookies: Dict[str, str]):
        """
        Create an authenticated 115 client from cookies.
        
        Args:
            cookies: Dictionary of cookies
        
        Returns:
            P115Client instance or None
        """
        try:
            if not self.validate_cookies(cookies):
                return None
            
            p115client = self._get_p115client_module()
            
            if hasattr(p115client, 'P115Client'):
                client = p115client.P115Client(cookies=cookies)
                self._client = client
                return client
            
            return None
        except Exception:
            return None
    
    def get_session_health(self, cookies: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Get session health status.
        
        Args:
            cookies: Optional cookies to check
        
        Returns:
            Dict with session health info
        """
        try:
            if cookies:
                is_valid = self.validate_cookies(cookies)
            else:
                is_valid = self._client is not None and self.validate_cookies(
                    getattr(self._client, 'cookies', {})
                )
            
            return {
                'hasValidSession': is_valid,
                'lastCheck': datetime.now().isoformat(),
                'success': True
            }
        except Exception as e:
            return {
                'hasValidSession': False,
                'error': str(e),
                'success': False
            }
    
    def save_share(self, share_code: str, access_code: str = None, 
                   save_cid: str = '0', cookies: str = None) -> Dict[str, Any]:
        """
        转存 115 分享链接到指定目录。
        
        Args:
            share_code: 分享码 (如 sw3xxxx)
            access_code: 访问码/提取码
            save_cid: 保存目录 ID，默认根目录
            cookies: 可选的 cookies 字符串
        
        Returns:
            Dict with success flag and saved file info
        """
        try:
            p115client_mod = self._get_p115client_module()
            
            # 获取或创建 client
            if cookies:
                client = p115client_mod.P115Client(cookies=cookies)
            elif self._client:
                client = self._client
            else:
                return {
                    'success': False,
                    'error': '未登录 115 账号，请先登录'
                }
            
            # 构建分享链接 URL
            share_url = f"https://115.com/s/{share_code}"
            if access_code:
                share_url += f"?password={access_code}"
            
            # 先获取分享信息
            try:
                # 使用 share_snap 获取分享快照
                share_info = client.share_snap({'share_code': share_code, 'receive_code': access_code or ''})
                
                if not share_info or share_info.get('state', True) is False:
                    return {
                        'success': False,
                        'error': share_info.get('error', '无法获取分享信息，可能链接已失效或需要提取码')
                    }
                
                # 获取分享中的文件列表
                file_list = share_info.get('data', {}).get('list', [])
                if not file_list:
                    return {
                        'success': False,
                        'error': '分享中没有文件'
                    }
                
                # 获取所有文件 ID
                file_ids = [str(f.get('fid') or f.get('file_id') or f.get('id')) for f in file_list]
                
                # 使用 share_receive 转存文件
                receive_payload = {
                    'share_code': share_code,
                    'receive_code': access_code or '',
                    'file_id': ','.join(file_ids),
                    'cid': save_cid
                }
                
                result = client.share_receive(receive_payload)
                
                if result and result.get('state', False):
                    return {
                        'success': True,
                        'data': {
                            'file_id': file_ids[0] if len(file_ids) == 1 else file_ids,
                            'count': len(file_ids),
                            'save_cid': save_cid
                        },
                        'message': f'成功转存 {len(file_ids)} 个文件'
                    }
                else:
                    return {
                        'success': False,
                        'error': result.get('error', '转存失败')
                    }
                    
            except Exception as api_error:
                return {
                    'success': False,
                    'error': f'调用分享 API 失败: {str(api_error)}'
                }
                
        except ImportError:
            return {
                'success': False,
                'error': 'p115client 未安装'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'转存失败: {str(e)}'
            }
    
    def clear_session(self, session_id: str = None):
        """Clear cached session(s)."""
        if session_id:
            self._session_cache.pop(session_id, None)
        else:
            self._session_cache.clear()
        
        # Clear client
        if not session_id:
            self._client = None


# Global P115Service instance
_p115_service = None


def get_p115_service() -> P115Service:
    """Get or create global P115Service instance."""
    global _p115_service
    if _p115_service is None:
        _p115_service = P115Service()
    return _p115_service