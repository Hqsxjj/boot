import os
import json
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

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
                
                # 使用 login_qrcode_token_open 获取第三方应用二维码
                qr_token_result = p115client.P115Client.login_qrcode_token_open(actual_app_id)
                
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
                
                return {
                    'sessionId': session_id,
                    'qrcode': qrcode_url,
                    'login_method': 'open_app',
                    'login_app': 'open_app'
                }
            else:
                # 普通扫码模式：使用 login_qrcode_token
                actual_app_id = ALL_DEVICE_PROFILES.get(login_app, 8)  # Default to web
                
                qr_token_result = p115client.P115Client.login_qrcode_token()
                
                if qr_token_result.get('state') != 1:
                    return {
                        'error': f"Failed to get QR token: {qr_token_result.get('message', 'Unknown error')}",
                        'success': False
                    }
                
                qr_data = qr_token_result.get('data', {})
                uid = qr_data.get('uid', '')
                
                # 构建二维码图片 URL
                qrcode_url = f"https://qrcodeapi.115.com/api/1.0/web/1.0/qrcode?uid={uid}"
                
                # Cache session info - 普通扫码模式
                self._session_cache[session_id] = {
                    'uid': uid,
                    'qr_data': qr_data,
                    'login_method': login_method,
                    'login_app': login_app,
                    'app_id': actual_app_id,
                    'started_at': datetime.now(),
                    'status': 'pending'
                }
                
                return {
                    'sessionId': session_id,
                    'qrcode': qrcode_url,
                    'login_method': login_method,
                    'login_app': login_app
                }
        except Exception as e:
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
                # API 调用失败，可能还在等待
                return {
                    'status': 'waiting',
                    'success': True
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
                return True  # Assume valid if we can create client
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