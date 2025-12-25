"""
p115_bridge.py - 115 网盘服务桥接

使用原生实现，无 p115client 依赖

主要类:
- StandardClientHolder: 标准扫码/Cookie 登录 (原生 requests)
- OpenAppClientHolder: 第三方 AppID 登录 (PKCE sha256)
- Pan115Service: 全局服务实例
"""

import os
import json
import uuid
import logging
import base64
import hashlib
import secrets
import requests
import threading
import time
from typing import Optional, Dict, Any, Union
from datetime import datetime

logger = logging.getLogger(__name__)

# 尝试导入原生 115 Open 客户端
P115OpenClient = None
P115CookieClient = None
try:
    from services.p115_open_client import P115OpenClient, P115CookieClient, create_open_client, create_cookie_client
    logger.info("已导入原生 P115OpenClient 和 P115CookieClient")
except ImportError:
    logger.warning("P115OpenClient 导入失败")

# 支持的客户端列表及中文名称 (p115client >= 0.0.7)
LOGIN_APPS = {
    "tv": {"ssoent": "I1", "name": "电视端"},
    "android": {"ssoent": "F1", "name": "安卓"},
    "ios": {"ssoent": "D1", "name": "115生活iPhone版"},
    "qios": {"ssoent": "D2", "name": "115管理iPhone版"},
    "ipad": {"ssoent": "H1", "name": "115生活iPad版"},
    "qipad": {"ssoent": "H2", "name": "115管理iPad版"},
    "apple_tv": {"ssoent": "J1", "name": "115TV苹果版"},
    "115android": {"ssoent": "F3", "name": "115安卓"},
    "115ios": {"ssoent": "D3", "name": "115 iOS"},
    "desktop": {"ssoent": "A1", "name": "桌面端"},
    "web": {"ssoent": "P1", "name": "网页版"},
    "harmony": {"ssoent": "S1", "name": "鸿蒙"},
    "qandroid": {"ssoent": "M1", "name": "轻量版安卓"},
}

SUPPORTED_APPS = list(LOGIN_APPS.keys())


class OpenAppClientHolder:
    """
    115 开放平台 (Open AppID) 客户端持有者 - 使用原生 P115OpenClient
    
    封装 P115OpenClient，提供与旧接口兼容的 API
    """

    def __init__(self, client_id: str = "", client_secret: str = "", token_service=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token_service = token_service
        self._lock = threading.RLock()
        
        # 创建原生客户端
        self._client: Optional[P115OpenClient] = None
        self._init_client()
    
    def _init_client(self):
        """初始化原生客户端"""
        if P115OpenClient is None:
            logger.warning("[115 Open] P115OpenClient 未导入")
            return
        
        try:
            # 从数据库加载或创建新客户端
            if self._token_service:
                self._client = create_open_client(self._token_service)
            else:
                self._client = P115OpenClient(app_id=self.client_id)
            
            if self._client and self._client.is_logged_in:
                logger.info(f"[115 Open] 客户端已初始化 (用户: {self._client.user_info().get('user_name', 'Unknown')})")
        except Exception as e:
            logger.warning(f"[115 Open] 初始化客户端失败: {e}")
            self._client = P115OpenClient(token_service=self._token_service, app_id=self.client_id)
    
    @property
    def client(self):
        """返回原生客户端（兼容旧代码）"""
        return self._client
    
    def start_open_qrcode(self) -> Dict[str, Any]:
        """获取 OpenID 二维码"""
        with self._lock:
            if P115OpenClient is None:
                return {"state": False, "msg": "P115OpenClient 未导入"}
            
            if not self._client:
                self._client = P115OpenClient(token_service=self._token_service, app_id=self.client_id)
            
            result = self._client.generate_qrcode(self.client_id)
            
            if result.get("success"):
                return {
                    "state": True,
                    "uid": result.get("uid"),
                    "qrcode": result.get("qrcode"),
                    "msg": "QR token received"
                }
            else:
                return {"state": False, "msg": result.get("error", "获取二维码失败")}
    
    def poll_open_qrcode(self) -> Dict[str, Any]:
        """轮询 OpenID 扫码状态"""
        with self._lock:
            if not self._client:
                return {"state": False, "msg": "客户端未初始化"}
            
            result = self._client.poll_qrcode_status()
            
            if result.get("status") == "success":
                return {
                    "state": True,
                    "status": "success",
                    "access_token": result.get("access_token"),
                    "refresh_token": result.get("refresh_token"),
                    "cookies": {
                        "access_token": result.get("access_token"),
                        "refresh_token": result.get("refresh_token")
                    },
                    "user": result.get("user", {})
                }
            
            status = result.get("status", "waiting")
            if status == "error":
                return {"state": False, "status": "error", "msg": result.get("error")}
            
            return {"state": True, "status": status}
    
    def init_with_token(self, access_token: str) -> bool:
        """使用 access_token 初始化客户端"""
        if not self._client:
            return False
        # 原生客户端在登录时已初始化
        return self._client.is_logged_in
    
    def refresh_access_token(self) -> Optional[str]:
        """刷新 access_token"""
        if not self._client:
            return None
        if self._client.refresh_access_token():
            return self._client._access_token
        return None
    
    def get_valid_client(self) -> Optional[P115OpenClient]:
        """获取有效的客户端实例"""
        if self._client and self._client.is_logged_in:
            return self._client
        return None


class StandardClientHolder:
    """
    115 标准 (Cookie/扫码) 客户端持有者 - 使用原生 P115CookieClient
    
    封装 P115CookieClient，提供与旧接口兼容的 API
    """

    def __init__(self, token_service=None):
        self._token_service = token_service
        self._lock = threading.RLock()
        
        # 创建原生客户端
        self._client: Optional[P115CookieClient] = None
        self._init_client()
    
    def _init_client(self):
        """初始化原生客户端"""
        if P115CookieClient is None:
            logger.warning("[115 Cookie] P115CookieClient 未导入")
            return
        
        try:
            # 方式1: 尝试从 token_service (数据库) 加载
            if self._token_service:
                self._client = create_cookie_client(self._token_service)
                if self._client and self._client.is_logged_in:
                    logger.info(f"[115 Cookie] 客户端已从数据库初始化")
                    return
            
            # 方式2: 尝试从 SecretStore 加载 (扫码登录保存在这里)
            try:
                from services.secret_store import SecretStore
                from models.database import get_session_factory
                secret_store = SecretStore(get_session_factory('secrets'))
                cookies_json = secret_store.get_secret('cloud115_cookies')
                if cookies_json:
                    import json
                    cookies = json.loads(cookies_json) if isinstance(cookies_json, str) else cookies_json
                    if isinstance(cookies, dict):
                        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
                    else:
                        cookie_str = str(cookies)
                    self._client = P115CookieClient(cookies=cookie_str)
                    if self._client and self._client.is_logged_in:
                        logger.info("[115 Cookie] 客户端已从 SecretStore 初始化")
                        return
            except Exception as e:
                logger.debug(f"[115 Cookie] 从 SecretStore 加载失败: {e}")
            
            # 方式3: 创建空客户端
            self._client = P115CookieClient()
        except Exception as e:
            logger.warning(f"[115 Cookie] 初始化客户端失败: {e}")
            self._client = P115CookieClient(token_service=self._token_service)
    
    @property
    def client(self):
        """返回原生客户端（兼容旧代码）"""
        return self._client
    
    @property
    def cookies(self) -> Optional[str]:
        """返回 Cookie 字符串"""
        return self._client._cookies if self._client else None
    
    @property
    def user_info(self) -> Dict[str, Any]:
        """返回用户信息"""
        return self._client.user_info() if self._client else {}
    
    def start_qrcode(self, app: str = "tv") -> dict:
        """获取扫码二维码"""
        with self._lock:
            if P115CookieClient is None:
                return {"state": False, "msg": "P115CookieClient 未导入"}
            
            if not self._client:
                self._client = P115CookieClient(token_service=self._token_service)
            
            result = self._client.generate_qrcode(app)
            
            if result.get("success"):
                return {
                    "state": True,
                    "uid": result.get("uid"),
                    "time": result.get("time"),
                    "sign": result.get("sign"),
                    "qrcode": result.get("qrcode"),
                    "app": result.get("app")
                }
            else:
                return {"state": False, "msg": result.get("error", "获取二维码失败")}

    def poll_qrcode(self) -> dict:
        """轮询扫码状态 - 使用 holder 中存储的 token"""
        return self.poll_qrcode_with_token(None)
    
    def poll_qrcode_with_token(self, qr_token: dict = None, login_app: str = "tv") -> dict:
        """轮询扫码状态"""
        with self._lock:
            if not self._client:
                return {"state": False, "msg": "客户端未初始化", "status": "error"}
            
            # 构造 token 格式
            token = None
            if qr_token and qr_token.get("uid"):
                token = {
                    "uid": qr_token.get("uid"),
                    "time": qr_token.get("time"),
                    "sign": qr_token.get("sign"),
                    "app": qr_token.get("app") or login_app
                }
            
            result = self._client.poll_qrcode_status(token)
            
            if result.get("status") == "success":
                return {
                    "state": True,
                    "status": "success",
                    "cookies": result.get("cookies", {}),
                    "user": result.get("user", {})
                }
            
            status = result.get("status", "waiting")
            if status == "error":
                return {"state": False, "status": "error", "msg": result.get("error")}
            
            return {"state": True, "status": status}

    def init_with_cookie(self, cookies: str, save: bool = True) -> bool:
        """使用 Cookie 初始化客户端"""
        with self._lock:
            if P115CookieClient is None:
                return False
            
            try:
                self._client = P115CookieClient(cookies=cookies, token_service=self._token_service if save else None)
                if self._client.is_logged_in:
                    # 获取用户信息触发保存
                    self._client._fetch_user_info()
                    if save and self._token_service:
                        # 解析 Cookie 字典
                        cookies_dict = {}
                        for part in cookies.split(';'):
                            if '=' in part:
                                k, v = part.strip().split('=', 1)
                                cookies_dict[k] = v
                        self._client._save_cookie(cookies_dict)
                    return True
            except Exception as e:
                logger.error(f"[115 Cookie] Init Cookie Error: {e}")
            return False

    def get_valid_client(self) -> Optional[P115CookieClient]:
        """获取有效的客户端实例"""
        if self._client and self._client.is_logged_in:
            return self._client
        return None

    # ========== 文件操作方法（委托给原生客户端）==========

    def fs_files(self, cid=0, limit=1000):
        if not self._client or not self._client.is_logged_in:
            return {"state": False, "error": "not init"}
        result = self._client.list_directory(cid, limit)
        return result if result else {"state": False, "error": "failed"}

    def fs_mkdir(self, pid, name):
        # Cookie 模式暂不支持高级操作
        return {"state": False, "error": "use Open API"}

    def fs_rename(self, fid, new_name):
        return {"state": False, "error": "use Open API"}

    def fs_move(self, fids, to_cid):
        # Cookie 模式暂不支持
        return {"state": False, "error": "use Open API"}

    def fs_delete(self, fids):
        # Cookie 模式暂不支持
        return {"state": False, "error": "use Open API"}

    def offline_add_url(self, url, save_cid):
        # Cookie 模式暂不支持
        return {"state": False, "error": "use Open API"}

    def share_receive(self, share_code, receive_code, to_cid, file_ids=None):
        """转存分享文件"""
        with self._lock:
            if not self._client:
                return {"state": False, "error": "客户端未初始化"}
            
            # 使用原生客户端的 share_receive 方法
            return self._client.share_receive(share_code, receive_code, to_cid, file_ids)

    def get_user_info(self) -> Dict[str, Any]:
        """获取用户信息"""
        with self._lock:
            if self._client:
                return self._client.user_info()
            return {}

    def get_storage_info(self) -> Dict[str, Any]:
        # Cookie 模式暂不支持
        return {}

    def get_offline_quota(self) -> Dict[str, Any]:
        # Cookie 模式暂不支持
        return {}


class P115Service:
    """115 网盘服务"""

    def __init__(self, token_service=None):
        self._token_service = token_service
        self._standard_holder: Optional[StandardClientHolder] = None
        self._open_holder: Optional[OpenAppClientHolder] = None
        self._session_cache: Dict[str, dict] = {}
        self._lock = threading.RLock()

    def _ensure_standard_holder(self) -> StandardClientHolder:
        if not self._standard_holder:
            self._standard_holder = StandardClientHolder(self._token_service)
        return self._standard_holder

    def _ensure_open_holder(self, client_id: str = "", client_secret: str = "") -> OpenAppClientHolder:
        if not self._open_holder or (client_id and self._open_holder.client_id != client_id):
            self._open_holder = OpenAppClientHolder(client_id, client_secret, self._token_service)
        return self._open_holder

    def start_qr_login(self, login_app: str = "tv", login_method: str = "qrcode", app_id: str = None) -> Dict[str, Any]:
        """开始二维码登录"""
        session_id = str(uuid.uuid4())

        if login_method == "open_app" and app_id:
            holder = self._ensure_open_holder(app_id, os.getenv("OPEN_APP_SECRET", ""))
            result = holder.start_open_qrcode()
        else:
            holder = self._ensure_standard_holder()
            result = holder.start_qrcode(app=login_app)

        if result.get("state"):
            self._session_cache[session_id] = {
                "uid": result.get("uid"),
                "time": result.get("time"),
                "sign": result.get("sign"),
                "status": "waiting",
                "login_method": login_method,
                "login_app": login_app,
                "app_id": app_id,
                "created_at": datetime.now().isoformat()
            }
            return {
                "success": True,
                "sessionId": session_id,
                "qrcode": result.get("qrcode", ""),
                "login_method": login_method,
                "login_app": login_app
            }
        else:
            return {"success": False, "error": result.get("msg", "获取二维码失败")}

    def poll_login_status(self, session_id: str, timeout: int = 30) -> Dict[str, Any]:
        """轮询登录状态 - 长轮询模式，等待状态变化或超时
        
        Args:
            session_id: 登录会话 ID
            timeout: 最长等待时间（秒），默认 30 秒
            
        Returns:
            包含 success, status, cookies 等字段的字典
        """
        session_info = self._session_cache.get(session_id)
        if not session_info:
            return {"success": False, "error": "Session not found", "status": "error"}

        login_method = session_info.get("login_method", "qrcode")
        login_app = session_info.get("login_app", "tv")
        last_status = session_info.get("status", "waiting")

        # 构造用于轮询的 token 数据
        qr_token = {
            "uid": session_info.get("uid"),
            "time": session_info.get("time"),
            "sign": session_info.get("sign"),
            "app": login_app
        }

        poll_interval = 2  # 每 2 秒轮询一次
        end_time = time.time() + timeout

        while time.time() < end_time:
            if login_method == "open_app":
                holder = self._ensure_open_holder(session_info.get("app_id", ""))
                result = holder.poll_open_qrcode()
            else:
                holder = self._ensure_standard_holder()
                result = holder.poll_qrcode_with_token(qr_token, login_app)

            current_status = result.get("status", "waiting")

            # 终态：立即返回
            if current_status == "success":
                return {
                    "success": True,
                    "status": "success",
                    "cookies": result.get("cookies", {}),
                    "user": result.get("user", {})
                }
            elif current_status == "expired":
                return {"success": False, "status": "expired", "error": "二维码已过期"}
            elif current_status == "error":
                return {"success": False, "status": "error", "error": result.get("msg", "轮询失败")}
            
            # 状态变化：更新 session 并返回
            if current_status != last_status:
                session_info["status"] = current_status
                return {"success": True, "status": current_status}
            
            # 等待下一次轮询
            time.sleep(poll_interval)

        # 超时：返回当前状态
        return {"success": True, "status": last_status}

    def clear_session(self, session_id: str):
        """清理登录会话"""
        if session_id in self._session_cache:
            del self._session_cache[session_id]

    def validate_cookies(self, cookies: dict) -> bool:
        """验证 Cookie 有效性"""
        holder = self._ensure_standard_holder()
        if isinstance(cookies, dict):
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        else:
            cookie_str = str(cookies)
        return holder.init_with_cookie(cookie_str, save=False)

    def get_session_health(self, cookies: dict) -> Dict[str, Any]:
        """检查会话健康状态"""
        holder = self._ensure_standard_holder()
        client = holder.get_valid_client()
        if client:
            try:
                ui = client.user_info()
                if ui and ui.get("state"):
                    return {"hasValidSession": True, "lastCheck": datetime.now().isoformat()}
            except:
                pass
        return {"hasValidSession": False}

    # ========== 文件操作代理 ==========

    def get_share_files(self, share_code: str, access_code: str = None, cookies: str = None, cid: str = "0") -> Dict[str, Any]:
        """获取分享文件列表"""
        holder = self._ensure_standard_holder()
        client = holder.get_valid_client()
        if not client:
            return {"success": False, "error": "未登录"}
        try:
            # 使用 share_snap 获取分享信息
            result = client.share_snap({"share_code": share_code, "receive_code": access_code or "", "cid": cid})
            if result and result.get("state"):
                files = result.get("data", {}).get("list", [])
                formatted = []
                for f in files:
                    # 目录判断：115 API 中目录有 cid 而没有 fid，文件有 fid
                    # 也检查 fc 和 ico 字段
                    has_cid = f.get("cid") is not None
                    has_fid = f.get("fid") is not None
                    is_folder_by_field = f.get("fc") == "folder" or f.get("ico") == "folder"
                    is_dir = is_folder_by_field or (has_cid and not has_fid)
                    
                    formatted.append({
                        "id": str(f.get("cid") or f.get("fid")),
                        "name": f.get("n") or f.get("file_name"),
                        "size": f.get("s") or f.get("file_size", 0),
                        "is_directory": is_dir
                    })
                return {"success": True, "data": formatted}
            return {"success": False, "error": result.get("error", "获取分享失败")}
        except Exception as e:
            logger.error(f"获取分享文件失败: {e}")
            return {"success": False, "error": str(e)}

    def save_share(self, share_code: str, access_code: str = None, save_cid: str = "0", cookies: str = None, file_ids: list = None) -> Dict[str, Any]:
        """转存分享"""
        holder = self._ensure_standard_holder()
        client = holder.get_valid_client()
        if not client:
            return {"success": False, "error": "未登录"}
        try:
            # 传递 file_ids 支持单个文件转存
            result = holder.share_receive(share_code, access_code or "", int(save_cid), file_ids)
            if result and result.get("state"):
                return {"success": True, "data": {"count": len(file_ids) if file_ids else 1}}
            return {"success": False, "error": result.get("error", "转存失败")}
        except Exception as e:
            logger.error(f"转存分享失败: {e}")
            return {"success": False, "error": str(e)}


# 全局服务实例
_p115_service: Optional[P115Service] = None


def get_p115_service(token_service=None) -> P115Service:
    """获取全局 P115Service 实例"""
    global _p115_service
    if _p115_service is None:
        _p115_service = P115Service(token_service)
    elif token_service is not None and _p115_service._token_service is None:
        # 如果已存在但没有 token_service，更新它
        _p115_service._token_service = token_service
        # 同时更新已存在的 holder
        if _p115_service._standard_holder:
            _p115_service._standard_holder._token_service = token_service
        if _p115_service._open_holder:
            _p115_service._open_holder._token_service = token_service
    return _p115_service


def init_p115_service(token_service) -> P115Service:
    """初始化 P115Service 并设置全局实例"""
    global _p115_service
    _p115_service = P115Service(token_service)
    return _p115_service
