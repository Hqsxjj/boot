import os
import json
import uuid
import logging
import base64
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 115 登录端配置 - 精简为 8 个移动端/平板端，包含中文名称
# key: API app 代码, ssoent: SSO入口, name: 显示名称
LOGIN_APPS = {
    'android': {'ssoent': 'F1', 'name': '安卓'},
    'ios': {'ssoent': 'D1', 'name': 'iOS'},
    'ipad': {'ssoent': 'H1', 'name': 'iPad'},
    '115android': {'ssoent': 'F3', 'name': '115安卓'},
    '115ios': {'ssoent': 'D3', 'name': '115 iOS'},
    'tv': {'ssoent': 'I1', 'name': '电视端'},
    'qandroid': {'ssoent': 'M1', 'name': '轻量版安卓'},
    'harmony': {'ssoent': 'S1', 'name': '鸿蒙'},
}

# 兼容旧代码的简化映射
ALL_DEVICE_PROFILES_FULL = {k: v['ssoent'] for k, v in LOGIN_APPS.items()}
ALL_DEVICE_PROFILES = ALL_DEVICE_PROFILES_FULL.copy()


class P115Service:
    """Service wrapper around p115client for 115 login functionality."""
    
    def __init__(self):
        """Initialize P115Service."""
        self._client = None
        self._session_cache = {}  # In-memory cache for login sessions
        self._session_timeout = timedelta(minutes=5)  # 总超时时间
        self._http_session = requests.Session()  # 用于 PKCE OAuth 请求
        self._polling_threads = {}  # 后台轮询线程
        
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
    
    def _background_poll_open_login(self, session_id: str):
        """
        后台线程：持续轮询 open_app 扫码状态直到成功或超时。
        参考 EmbyNginxDK 的 check_login 实现。
        """
        import time
        
        session_info = self._session_cache.get(session_id)
        if not session_info:
            return
        
        uid = session_info.get('uid', '')
        time_val = session_info.get('time', '')
        sign = session_info.get('sign', '')
        code_verifier = session_info.get('code_verifier', '')
        
        max_wait_time = 360  # 最多等待6分钟
        elapsed_time = 0
        scanned = False  # 标记是否已扫描
        
        while elapsed_time < max_wait_time:
            # 检查 session 是否还存在
            if session_id not in self._session_cache:
                logger.info(f"Session {session_id} 已被清理，停止轮询")
                break
            
            status_result = self.check_open_login_status(uid, time_val, sign)
            status_code = status_result.get('status', -1)
            
            if status_code == 2:
                # 用户已确认，获取 access_token
                token_data = self.get_open_access_token(uid, code_verifier)
                if token_data:
                    session_info['status'] = 'success'
                    session_info['token_data'] = token_data
                    session_info['cookies'] = token_data
                    logger.info(f"Session {session_id} 扫码登录成功！")
                else:
                    session_info['status'] = 'error'
                    session_info['error'] = '获取 access_token 失败'
                break
            elif status_code == 1:
                # 已扫描，等待确认 - 立刻更新状态并切换到快速轮询
                if not scanned:
                    scanned = True
                    logger.info(f"Session {session_id} 已扫描，切换到快速轮询模式")
                session_info['status'] = 'scanned'
            elif status_code == 0:
                # 未扫描
                session_info['status'] = 'waiting'
            elif status_code == -1:
                # 过期
                session_info['status'] = 'expired'
                logger.info(f"Session {session_id} 二维码过期")
                break
            
            # 动态轮询间隔：未扫描时2分钟，已扫描后1秒快速响应
            if scanned:
                sleep_time = 1  # 已扫描后1秒轮询，确保快速响应
            else:
                sleep_time = 120  # 未扫描时2分钟轮询
            
            time.sleep(sleep_time)
            elapsed_time += sleep_time
        
        # 超时处理
        if elapsed_time >= max_wait_time and session_info.get('status') not in ['success', 'expired']:
            session_info['status'] = 'expired'
            logger.info(f"Session {session_id} 轮询超时")
    
    def _background_poll_qrcode_login(self, session_id: str):
        """
        后台线程：持续轮询普通 qrcode 扫码状态直到成功或超时。
        解决同步轮询导致的前端超时问题。
        """
        import time
        
        session_info = self._session_cache.get(session_id)
        if not session_info:
            return
        
        qr_data = session_info.get('qr_data', {})
        uid = qr_data.get('uid', '')
        time_val = qr_data.get('time', 0)
        sign = qr_data.get('sign', '')
        login_app = session_info.get('login_app', 'web')
        
        if not uid:
            logger.error(f"Session {session_id} 缺少 uid")
            return
        
        payload = {'uid': uid, 'time': time_val, 'sign': sign}
        
        max_wait_time = 300  # 最多等待 5 分钟
        elapsed_time = 0
        scanned = False
        consecutive_errors = 0
        
        p115client = self.p115client
        if not p115client:
            session_info['status'] = 'error'
            session_info['error'] = 'p115client not available'
            return
        
        while elapsed_time < max_wait_time:
            if session_id not in self._session_cache:
                logger.info(f"Session {session_id} 已被清理，停止轮询")
                break
            
            try:
                try:
                    status_result = p115client.P115Client.login_qrcode_scan_status(payload, app=login_app)
                except TypeError:
                    status_result = p115client.P115Client.login_qrcode_scan_status(payload)
                
                status_code = status_result.get('data', {}).get('status', 0)
                consecutive_errors = 0  # 重置错误计数
                
                if status_code == 0:
                    session_info['status'] = 'waiting'
                elif status_code == 1:
                    if not scanned:
                        scanned = True
                        logger.info(f"Session {session_id} 已扫码，切换快速轮询")
                    session_info['status'] = 'scanned'
                elif status_code == 2:
                    # 用户确认，获取 cookies
                    try:
                        try:
                            scan_result = p115client.P115Client.login_qrcode_scan(payload, app=login_app)
                        except TypeError:
                            scan_result = p115client.P115Client.login_qrcode_scan(payload)
                        
                        if scan_result.get('state') == 1:
                            cookie_data = scan_result.get('data', {}).get('cookie', {})
                            if isinstance(cookie_data, str):
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
                            logger.info(f"Session {session_id} 扫码登录成功!")
                        else:
                            session_info['status'] = 'error'
                            session_info['error'] = '获取 cookies 失败'
                    except Exception as e:
                        session_info['status'] = 'error'
                        session_info['error'] = str(e)
                    break
                elif status_code in [-1, -2]:
                    session_info['status'] = 'expired'
                    logger.info(f"Session {session_id} 二维码过期")
                    break
                    
            except Exception as e:
                consecutive_errors += 1
                logger.warning(f"Session {session_id} 轮询出错 ({consecutive_errors}): {str(e)}")
                if consecutive_errors >= 5:
                    session_info['status'] = 'error'
                    session_info['error'] = f'轮询失败: {str(e)}'
                    break
            
            # 动态轮询间隔
            if scanned:
                sleep_time = 1
            else:
                sleep_time = 3
            time.sleep(sleep_time)
            elapsed_time += sleep_time
        
        if elapsed_time >= max_wait_time and session_info.get('status') not in ['success', 'expired', 'error']:
            session_info['status'] = 'expired'
            logger.info(f"Session {session_id} 轮询超时")
    
    # ==================== PKCE OAuth 开放 API 方法 ====================
    
    def _generate_pkce_params(self) -> tuple:
        """生成 PKCE 参数 (code_verifier, code_challenge)"""
        import secrets
        import hashlib
        
        code_verifier = secrets.token_urlsafe(96)[:128]
        code_challenge = base64.b64encode(
            hashlib.sha256(code_verifier.encode("utf-8")).digest()
        ).decode("utf-8")
        return code_verifier, code_challenge
    
    def generate_open_qrcode(self, app_id: int = 100197531) -> Optional[Dict[str, Any]]:
        """
        使用 PKCE 规范生成开放 API 二维码
        
        Args:
            app_id: 第三方应用 ID
            
        Returns:
            包含二维码 URL 和验证参数的字典
        """
        try:
            code_verifier, code_challenge = self._generate_pkce_params()
            
            resp = self._http_session.post(
                "https://passportapi.115.com/open/authDeviceCode",
                data={
                    "client_id": app_id,
                    "code_challenge": code_challenge,
                    "code_challenge_method": "sha256"
                },
                timeout=10
            )
            result = resp.json()
            
            if result.get("code") != 0:
                logger.warning(f"authDeviceCode failed: {result.get('message')}")
                return None
            
            data = result.get("data", {})
            return {
                "qrcode_url": data.get("qrcode", ""),
                "code_verifier": code_verifier,
                "uid": data.get("uid", ""),
                "time": str(data.get("time", "")),
                "sign": data.get("sign", "")
            }
        except Exception as e:
            logger.error(f"generate_open_qrcode failed: {str(e)}")
            return None
    
    def check_open_login_status(self, uid: str, time: str, sign: str) -> Dict[str, Any]:
        """
        检查开放 API 扫码状态
        
        Returns:
            {"status": 0/1/2, "message": "..."} 其中 0=未扫描, 1=已扫描, 2=已确认
        """
        try:
            resp = self._http_session.get(
                "https://qrcodeapi.115.com/get/status/",
                params={
                    "uid": uid,
                    "time": int(time) if time else 0,
                    "sign": sign
                },
                timeout=10
            )
            result = resp.json()
            data = result.get("data", {})
            
            if not data:
                return {"status": -1, "message": "二维码已过期"}
            
            return {"status": data.get("status", 0), "message": "OK"}
        except Exception as e:
            logger.error(f"check_open_login_status failed: {str(e)}")
            return {"status": -1, "message": str(e)}
    
    def get_open_access_token(self, uid: str, code_verifier: str) -> Optional[Dict[str, Any]]:
        """
        获取开放 API access_token
        
        Returns:
            {"access_token": "...", "refresh_token": "...", "expires_in": 7200}
        """
        try:
            resp = self._http_session.post(
                "https://passportapi.115.com/open/deviceCodeToToken",
                data={
                    "uid": uid,
                    "code_verifier": code_verifier
                },
                timeout=10
            )
            result = resp.json()
            
            if result.get("code") != 0:
                logger.error(f"deviceCodeToToken failed: {result.get('message')}")
                return None
            
            return result.get("data")
        except Exception as e:
            logger.error(f"get_open_access_token failed: {str(e)}")
            return None
    
    def refresh_open_access_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """刷新开放 API access_token"""
        try:
            resp = self._http_session.post(
                "https://passportapi.115.com/open/refreshToken",
                data={"refresh_token": refresh_token},
                timeout=10
            )
            result = resp.json()
            
            if result.get("code") != 0:
                logger.error(f"refreshToken failed: {result.get('message')}")
                return None
            
            return result.get("data")
        except Exception as e:
            logger.error(f"refresh_open_access_token failed: {str(e)}")
            return None
    
    def _get_qrcode_token_direct(self) -> Dict[str, Any]:
        """
        直接调用 115 官方 API 获取二维码 Token，绕过 p115client。
        
        API: https://qrcodeapi.115.com/api/1.0/web/1.0/token/
        
        Returns:
            Dict with uid, time, sign, qrcode (扫码内容URL)
        """
        try:
            url = "https://qrcodeapi.115.com/api/1.0/web/1.0/token/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://115.com/'
            }
            
            response = self._http_session.get(url, headers=headers, timeout=15)
            result = response.json()
            
            logger.info(f"Direct 115 API response: state={result.get('state')}")
            
            if result.get('state') == 1:
                data = result.get('data', {})
                uid = data.get('uid', '')
                if uid:
                    return {
                        'success': True,
                        'uid': uid,
                        'time': data.get('time', 0),
                        'sign': data.get('sign', ''),
                        'qrcode': data.get('qrcode', f'https://115.com/scan/dg-{uid}')
                    }
                else:
                    logger.warning(f"115 API returned but no uid: {result}")
                    return {'success': False, 'error': 'No UID in response'}
            else:
                error_msg = result.get('message', result.get('msg', 'Unknown error'))
                logger.warning(f"115 API error: {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except requests.exceptions.Timeout:
            logger.warning("Direct 115 API timeout")
            return {'success': False, 'error': '115 API 请求超时'}
        except Exception as e:
            logger.error(f"Direct 115 API exception: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _fetch_qrcode_as_base64(self, qrcode_url: str, uid: str = '') -> str:
        """
        下载二维码图片并转换为 base64 data URI。
        优先使用115官方API下载（确保正确格式），本地生成作为备选。
        
        Args:
            qrcode_url: 二维码图片URL
            uid: UID（用于备选方案）
        
        Returns:
            base64 data URI 格式的图片数据
        """
        logger.info(f"Fetching QR code for uid: {uid[:16] if uid else 'N/A'}...")
        
        # 方案1 (优先): 从115官方API下载二维码图片
        if qrcode_url:
            for attempt in range(3):  # 最多重试 3 次
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Referer': 'https://115.com/',
                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
                    }
                    
                    # 增加超时时间到10秒
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
                        break  # 无效响应，不重试
                        
                except requests.Timeout:
                    logger.warning(f"Attempt {attempt + 1}: 115 API request timeout")
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1}: Failed to fetch QR code from 115 API: {str(e)}")
        
        # 方案2 (备选): 使用第三方二维码生成服务
        if uid:
            # 正确的115扫码URL格式 (从p115client.login_qrcode_token返回的qrcode字段学到的)
            qr_content = f"https://115.com/scan/dg-{uid}"
            fallback_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={requests.utils.quote(qr_content)}"
            
            try:
                response = requests.get(fallback_url, timeout=10)
                if response.status_code == 200 and len(response.content) > 100:
                    img_base64 = base64.b64encode(response.content).decode('utf-8')
                    data_uri = f"data:image/png;base64,{img_base64}"
                    logger.info(f"QR code fetched from third-party service with correct 115 scan URL")
                    return data_uri
            except Exception as e:
                logger.warning(f"Third-party QR service failed: {str(e)}")
        
        # 方案3 (最后备选): 本地生成二维码
        if uid:
            try:
                import qrcode
                from io import BytesIO
                
                # 115扫码登录的正确URL格式
                qr_content = f"https://115.com/scan/dg-{uid}"
                
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
                
                logger.info(f"QR code generated locally for uid: {uid[:8]}... with correct 115 scan URL")
                return data_uri
                
            except ImportError:
                logger.warning("qrcode library not installed")
            except Exception as e:
                logger.warning(f"Failed to generate QR code locally: {str(e)}")
        
        # 最后返回原始URL（让前端尝试直接加载）
        logger.warning("All QR code generation methods failed, returning original URL")
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
                # 第三方应用模式：使用 PKCE OAuth 流程
                if not app_id:
                    return {
                        'error': 'App ID is required for open_app login method',
                        'success': False
                    }
                
                actual_app_id = int(app_id) if isinstance(app_id, str) and app_id.isdigit() else app_id
                if isinstance(actual_app_id, str):
                    return {
                        'error': f'Invalid app_id: {app_id}. Must be a numeric ID.',
                        'success': False
                    }
                logger.info(f"open_app mode: using PKCE OAuth with app_id={actual_app_id}")
                
                # 使用 PKCE OAuth 流程生成二维码
                qr_result = self.generate_open_qrcode(actual_app_id)
                
                if not qr_result:
                    return {
                        'error': '获取第三方应用二维码失败',
                        'success': False
                    }
                
                qrcode_url = qr_result.get('qrcode_url', '')
                uid = qr_result.get('uid', '')
                
                # Cache session info - 保存 code_verifier 用于后续获取 token
                self._session_cache[session_id] = {
                    'uid': uid,
                    'time': qr_result.get('time', ''),
                    'sign': qr_result.get('sign', ''),
                    'code_verifier': qr_result.get('code_verifier', ''),
                    'qr_data': qr_result,
                    'login_method': 'open_app',
                    'login_app': 'open_app',
                    'app_id': actual_app_id,
                    'started_at': datetime.now(),
                    'status': 'waiting'  # 初始状态
                }
                
                # 获取二维码图片
                qrcode_base64 = self._fetch_qrcode_as_base64(qrcode_url, uid) if qrcode_url else ''
                
                # 启动后台轮询线程 - 参考 EmbyNginxDK 的实现
                import threading
                polling_thread = threading.Thread(
                    target=self._background_poll_open_login,
                    args=(session_id,),
                    daemon=True
                )
                polling_thread.start()
                self._polling_threads[session_id] = polling_thread
                logger.info(f"已启动后台轮询线程: session_id={session_id}")
                
                return {
                    'sessionId': session_id,
                    'qrcode': qrcode_base64,
                    'login_method': 'open_app',
                    'login_app': 'open_app'
                }
            else:
                # 普通扫码模式：优先使用直接 API 调用，p115client 作为备选
                logger.info(f"Starting QR login: login_app={login_app}, login_method={login_method}")
                
                uid = None
                qr_data = {}
                last_error = None
                
                # 方法1: 直接调用 115 官方 API（更可靠）
                direct_result = self._get_qrcode_token_direct()
                if direct_result.get('success'):
                    uid = direct_result.get('uid', '')
                    qr_data = {
                        'uid': uid,
                        'time': direct_result.get('time', 0),
                        'sign': direct_result.get('sign', ''),
                        'qrcode': direct_result.get('qrcode', f'https://115.com/scan/dg-{uid}')
                    }
                    logger.info(f"Got QR token from direct API: uid={uid[:8]}...")
                else:
                    last_error = direct_result.get('error', 'Unknown error')
                    logger.warning(f"Direct API failed: {last_error}, trying p115client...")
                    
                    # 方法2: 使用 p115client 作为备选
                    try:
                        qr_token_result = p115client.P115Client.login_qrcode_token()
                        if qr_token_result.get('state') == 1:
                            qr_data = qr_token_result.get('data', {})
                            uid = qr_data.get('uid', '')
                            logger.info(f"Got QR token from p115client: uid={uid[:8] if uid else 'N/A'}...")
                        else:
                            last_error = qr_token_result.get('message', 'p115client returned non-1 state')
                    except Exception as e:
                        last_error = str(e)
                        logger.error(f"p115client also failed: {e}")
                
                if not uid:
                    logger.error(f"No UID in QR token response: {qr_data}")
                    return {
                        'error': 'No UID returned from 115 API',
                        'success': False
                    }
                
                # qr_data['qrcode'] 是扫码内容URL (如 https://115.com/scan/dg-{uid})
                # qrcodeapi.115.com 是获取QR图片的API
                # 保存扫码内容URL用于备选方案
                scan_url = qr_data.get('qrcode', f"https://115.com/scan/dg-{uid}")
                
                # 使用官方API获取QR图片
                qrcode_image_url = f"https://qrcodeapi.115.com/api/1.0/web/1.0/qrcode?uid={uid}"
                
                logger.info(f"QR login started: uid={uid[:8]}..., scan_url={scan_url[:40]}...")
                
                # Cache session info - 普通扫码模式
                self._session_cache[session_id] = {
                    'uid': uid,
                    'qr_data': qr_data,
                    'scan_url': scan_url,  # 保存扫码内容URL
                    'login_method': login_method,
                    'login_app': login_app,
                    'app_id': app_id,  # 可能为 None，普通模式不需要
                    'started_at': datetime.now(),
                    'status': 'waiting'  # 改为 waiting 以便后台轮询
                }
                
                # 代理下载二维码并转 base64（传递uid用于本地生成备选）
                qrcode_base64 = self._fetch_qrcode_as_base64(qrcode_image_url, uid)
                
                # 启动后台轮询线程 - 解决前端超时问题
                import threading
                polling_thread = threading.Thread(
                    target=self._background_poll_qrcode_login,
                    args=(session_id,),
                    daemon=True
                )
                polling_thread.start()
                self._polling_threads[session_id] = polling_thread
                logger.info(f"已启动后台轮询线程 (qrcode 模式): session_id={session_id}")
                
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
            
            login_method = session_info.get('login_method', 'qrcode')
            
            # ================ open_app 模式：后台线程已轮询，直接读取状态 ================
            if login_method == 'open_app':
                # 后台线程已经在持续轮询 115 API，这里只需读取状态
                current_status = session_info.get('status', 'waiting')
                
                if current_status == 'success':
                    # 登录成功，后台线程已获取 token
                    return {
                        'status': 'success',
                        'cookies': session_info.get('cookies', {}),
                        'token_data': session_info.get('token_data', {}),
                        'success': True
                    }
                elif current_status == 'scanned':
                    return {'status': 'scanned', 'success': True}
                elif current_status == 'waiting':
                    return {'status': 'waiting', 'success': True}
                elif current_status == 'expired':
                    return {
                        'status': 'expired',
                        'message': session_info.get('error', '二维码已过期'),
                        'success': False
                    }
                elif current_status == 'error':
                    return {
                        'status': 'error',
                        'error': session_info.get('error', '登录失败'),
                        'success': False
                    }
                else:
                    return {'status': 'waiting', 'success': True}
            
            # ================ 普通 qrcode 模式：从缓存读取状态 ================
            # 后台线程已在持续轮询 115 API，这里只需读取缓存中的状态
            current_status = session_info.get('status', 'waiting')
            
            if current_status == 'success':
                return {
                    'status': 'success',
                    'cookies': session_info.get('cookies', {}),
                    'success': True
                }
            elif current_status == 'scanned':
                return {'status': 'scanned', 'success': True}
            elif current_status == 'waiting':
                return {'status': 'waiting', 'success': True}
            elif current_status == 'expired':
                return {
                    'status': 'expired',
                    'message': session_info.get('error', '二维码已过期'),
                    'success': False
                }
            elif current_status == 'error':
                return {
                    'status': 'error',
                    'error': session_info.get('error', '登录失败'),
                    'success': False
                }
            else:
                return {'status': 'waiting', 'success': True}
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
                logger.warning('validate_cookies: empty cookies provided')
                return False
            
            # 检查必要的cookie字段
            required_keys = ['UID', 'CID', 'SEID']
            has_required = any(key in cookies for key in required_keys)
            if not has_required:
                logger.warning(f'validate_cookies: missing required keys. Got: {list(cookies.keys())}')
                # 不立即返回False，尝试继续验证
            
            p115client = self._get_p115client_module()
            
            if not hasattr(p115client, 'P115Client'):
                logger.warning('validate_cookies: P115Client not found in p115client module')
                return False
            
            # Create client with cookies and test authentication
            try:
                client = p115client.P115Client(cookies=cookies)
                logger.info('validate_cookies: P115Client created successfully')
            except Exception as e:
                logger.warning(f'validate_cookies: P115Client creation failed: {e}')
                return False
            
            # 尝试多种方法验证
            validation_attempts = [
                ('get_user_id', lambda: client.get_user_id() if hasattr(client, 'get_user_id') else None),
                ('user_id', lambda: client.user_id if hasattr(client, 'user_id') else None),
                ('fs_files', lambda: client.fs_files({"cid": 0, "limit": 1}) if hasattr(client, 'fs_files') else None),
            ]
            
            for method_name, method_func in validation_attempts:
                try:
                    result = method_func()
                    if result is not None:
                        logger.info(f'validate_cookies: validation succeeded via {method_name}')
                        return True
                except Exception as e:
                    logger.debug(f'validate_cookies: {method_name} failed: {e}')
                    continue
            
            logger.warning('validate_cookies: all validation methods failed')
            return False
        except ImportError as e:
            logger.error(f'validate_cookies: p115client not available: {e}')
            return False
        except Exception as e:
            logger.error(f'validate_cookies: unexpected error: {e}')
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
    
    def get_share_files(self, share_code: str, access_code: str = None, cookies: str = None, cid: str = '0') -> Dict[str, Any]:
        """
        获取分享链接中的文件列表
        
        Args:
            share_code: 分享码
            access_code: 提取码
            cookies: Cookie 字符串
            cid: 子目录 ID，默认为 '0' 表示根目录
        """
        try:
            p115client_mod = self._get_p115client_module()
            
            # 获取或创建 client
            if cookies:
                # 处理 cookies 格式
                if isinstance(cookies, str):
                    try:
                        cookies_dict = json.loads(cookies)
                    except json.JSONDecodeError:
                        cookies_dict = cookies
                else:
                    cookies_dict = cookies
                client = p115client_mod.P115Client(cookies=cookies_dict)
            elif self._client:
                client = self._client
            else:
                return {
                    'success': False,
                    'error': '未登录 115 账号，请先登录'
                }
            
            # 构造 payload - 支持子目录 cid
            payload = {
                'share_code': share_code,
                'receive_code': access_code or '',
                'cid': int(cid) if cid else 0,
                'limit': 100,
                'offset': 0
            }
            
            logger.info(f'调用 share_snap API: share_code={share_code}, receive_code={access_code or "无"}')
            
            # 使用 share_snap 获取分享快照
            share_info = client.share_snap(payload)
            
            logger.info(f'share_snap 返回: state={share_info.get("state")}, keys={list(share_info.keys()) if share_info else "None"}')
            
            # 检查状态
            if not share_info:
                return {
                    'success': False,
                    'error': '无法获取分享信息，API 返回空'
                }
            
            if share_info.get('state', True) is False:
                error_msg = share_info.get('error') or share_info.get('message') or '未知错误'
                return {
                    'success': False,
                    'error': f'无法获取分享信息: {error_msg}'
                }
            
            # 获取分享中的文件列表 - 尝试多种可能的数据结构
            data = share_info.get('data', {})
            file_list = data.get('list', []) if isinstance(data, dict) else []
            
            # 如果 data 本身就是列表
            if isinstance(data, list):
                file_list = data
            
            logger.info(f'获取到 {len(file_list)} 个文件')
            
            # 格式化输出
            result_list = []
            for f in file_list:
                # 判断是否是文件夹 - 多种判断方式
                # fc 表示子文件数量，有值说明是文件夹
                # ico == 'folder' 表示文件夹
                # 有 cid 但没有 fid 也表示是文件夹
                is_dir = bool(f.get('fc') or f.get('ico') == 'folder' or (f.get('cid') and not f.get('fid')))
                
                # 文件夹使用 cid 作为 ID，文件使用 fid 作为 ID
                # 这样点击文件夹进入时可以正确使用 cid 参数
                if is_dir:
                    file_id = str(f.get('cid') or f.get('id') or f.get('fid') or '')
                else:
                    file_id = str(f.get('fid') or f.get('file_id') or f.get('id') or f.get('cid') or '')
                
                file_name = f.get('n') or f.get('name') or f.get('file_name') or '未知文件'
                file_size = f.get('s') or f.get('size') or f.get('file_size') or 0
                file_time = f.get('t') or f.get('time') or f.get('te') or ''
                
                result_list.append({
                    'id': file_id,
                    'name': file_name,
                    'size': file_size,
                    'is_directory': is_dir,
                    'time': file_time
                })
                
            return {
                'success': True,
                'data': result_list
            }
            
        except Exception as e:
            logger.error(f'获取分享文件列表失败: {str(e)}', exc_info=True)
            return {
                'success': False,
                'error': f'获取文件列表失败: {str(e)}'
            }

    def save_share(self, share_code: str, access_code: str = None, 
                   save_cid: str = '0', cookies: str = None, file_ids: list = None) -> Dict[str, Any]:
        """
        转存 115 分享链接到指定目录。
        
        Args:
            share_code: 分享码 (如 sw3xxxx)
            access_code: 访问码/提取码
            save_cid: 保存目录 ID，默认根目录
            cookies: 可选的 cookies 字符串
            file_ids: 可选的文件 ID 列表，如果提供则只转存这些文件
        
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
            
            # 如果指定了 file_ids，直接使用
            target_file_ids = []
            if file_ids and isinstance(file_ids, list) and len(file_ids) > 0:
                target_file_ids = file_ids
            else:
                # 否则获取所有文件
                share_info = client.share_snap({'share_code': share_code, 'receive_code': access_code or ''})
                
                if not share_info or share_info.get('state', True) is False:
                    return {
                        'success': False,
                        'error': share_info.get('error', '无法获取分享信息，可能链接已失效或需要提取码')
                    }
                
                file_list = share_info.get('data', {}).get('list', [])
                if not file_list:
                    return {
                        'success': False,
                        'error': '分享中没有文件'
                    }
                target_file_ids = [str(f.get('fid') or f.get('file_id') or f.get('id')) for f in file_list]
            
            if not target_file_ids:
                 return {
                    'success': False,
                    'error': '未选择要转存的文件'
                 }

            # 使用 share_receive 转存文件
            receive_payload = {
                'share_code': share_code,
                'receive_code': access_code or '',
                'file_id': ','.join(target_file_ids),
                'cid': save_cid
            }
            
            result = client.share_receive(receive_payload)
            
            if result and result.get('state', False):
                return {
                    'success': True,
                    'data': {
                        'message': '转存任务已提交',
                        'count': len(target_file_ids)
                    }
                }
            else:
                 error_msg = result.get('error') or result.get('message') or 'Unknown error'
                 return {
                    'success': False,
                    'error': f'转存失败: {error_msg}'
                 }
                 
        except Exception as e:
            logger.error(f'转存分享失败: {str(e)}')
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