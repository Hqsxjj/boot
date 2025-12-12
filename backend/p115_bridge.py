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
                      login_method: str = 'cookie') -> Dict[str, Any]:
        """
        Start a QR code login session.
        
        Args:
            login_app: Device profile (web, ios, android, etc.)
            login_method: 'cookie' or 'open_app'
        
        Returns:
            Dict with sessionId and qrcode URL
        """
        try:
            p115client = self._get_p115client_module()
            
            session_id = str(uuid.uuid4())
            
            # Get device app_id for the requested profile
            app_id = ALL_DEVICE_PROFILES.get(login_app, 8)  # Default to web
            
            # Create login instance from cloud115.loginApp
            if hasattr(p115client, 'cloud115'):
                login_instance = p115client.cloud115.loginApp(app_id=app_id)
            else:
                # Fallback: create basic login instance
                login_instance = p115client.P115Client(login_method='qrcode')
            
            # Get QR code
            qr_code_data = login_instance.get_qr_code()
            
            # Cache session info
            self._session_cache[session_id] = {
                'login_instance': login_instance,
                'login_method': login_method,
                'login_app': login_app,
                'app_id': app_id,
                'started_at': datetime.now(),
                'status': 'pending'
            }
            
            return {
                'sessionId': session_id,
                'qrcode': qr_code_data.get('qrcode') if isinstance(qr_code_data, dict) else str(qr_code_data),
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
            
            login_instance = session_info['login_instance']
            
            # Poll for scan status
            try:
                # Attempt to get scan result
                if hasattr(login_instance, 'get_scan_status'):
                    status = login_instance.get_scan_status()
                elif hasattr(login_instance, 'check_login'):
                    status = login_instance.check_login()
                else:
                    status = {'status': 'waiting'}
                
                if isinstance(status, dict):
                    if status.get('status') == 'success' or status.get('success'):
                        # Login successful, get cookies
                        if hasattr(login_instance, 'get_cookies'):
                            cookies = login_instance.get_cookies()
                        elif hasattr(login_instance, 'cookies'):
                            cookies = login_instance.cookies
                        else:
                            cookies = {}
                        
                        session_info['status'] = 'success'
                        session_info['cookies'] = cookies
                        
                        return {
                            'status': 'success',
                            'cookies': cookies,
                            'success': True
                        }
                    elif status.get('status') in ['waiting', 'pending']:
                        return {
                            'status': 'waiting',
                            'success': True
                        }
                    elif status.get('status') == 'cancelled':
                        session_info['status'] = 'cancelled'
                        return {
                            'status': 'cancelled',
                            'success': False,
                            'error': 'User cancelled login'
                        }
            except Exception:
                pass
            
            # Still waiting
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