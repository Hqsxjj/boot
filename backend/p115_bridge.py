"""
p115_bridge.py - 115 网盘服务桥接
基于 tgbot 项目重构，使用 p115client 类方法进行扫码登录

主要类:
- StandardClientHolder: 标准扫码/Cookie 登录
- OpenAppClientHolder: 第三方 AppID 登录 (PKCE 模式)
- Pan115Service: 全局服务实例
"""

import os
import json
import uuid
import logging
import base64
import requests
import threading
import time
from typing import Optional, Dict, Any, Union
from datetime import datetime

logger = logging.getLogger(__name__)

# 尝试导入 p115client
P115Client = None
try:
    from p115client import P115Client
    logger.info("已导入 p115client 模块")
except ImportError:
    logger.warning("p115client 未安装，115 功能将受限")

# Open AppID 相关常量 (PKCE)
CODE_VERIFIER = "0" * 64
CODE_CHALLENGE = "670b14728ad9902aecba32e22fa4f6bd"

# 支持的客户端列表及中文名称
LOGIN_APPS = {
    "tv": {"ssoent": "I1", "name": "电视端"},
    "android": {"ssoent": "F1", "name": "安卓"},
    "ios": {"ssoent": "D1", "name": "iOS"},
    "ipad": {"ssoent": "H1", "name": "iPad"},
    "115android": {"ssoent": "F3", "name": "115安卓"},
    "115ios": {"ssoent": "D3", "name": "115 iOS"},
    "desktop": {"ssoent": "A1", "name": "桌面端"},
    "web": {"ssoent": "P1", "name": "网页版"},
    "harmony": {"ssoent": "S1", "name": "鸿蒙"},
    "qandroid": {"ssoent": "M1", "name": "轻量版安卓"},
}

SUPPORTED_APPS = list(LOGIN_APPS.keys())


class OpenAppClientHolder:
    """115 开放平台 (Open AppID) 客户端持有者 - PKCE 模式"""

    def __init__(self, client_id: str = "", client_secret: str = ""):
        self.client: Optional[P115Client] = None
        self.client_id = client_id
        self.client_secret = client_secret
        self._qr_token: Optional[dict] = None
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = threading.RLock()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def start_open_qrcode(self) -> Dict[str, Any]:
        """获取 OpenID 二维码"""
        with self._lock:
            if not self.client_id or not self.client_secret:
                return {"state": False, "msg": "Open AppID 需要配置 AppID 和 Secret"}

            if P115Client is None:
                return {"state": False, "msg": "p115client 未安装"}

            try:
                resp = P115Client.login_qrcode_token_open(
                    self.client_id,
                    code_challenge=CODE_CHALLENGE,
                    code_challenge_method="md5"
                )

                if resp.get("code") == 0 and resp.get("data"):
                    self._qr_token = resp["data"]
                    qr_url = self._qr_token.get("qrcode")
                    b64_img = ""
                    try:
                        if qr_url:
                            img_resp = requests.get(qr_url, headers=self.headers, timeout=10)
                            b64_img = base64.b64encode(img_resp.content).decode('utf-8')
                    except Exception as e:
                        logger.error(f"OpenID QR 图片下载失败: {e}")

                    return {
                        "state": True,
                        "uid": self._qr_token["uid"],
                        "qrcode": b64_img,
                        "msg": "QR token received"
                    }
                else:
                    return {"state": False, "msg": f"获取二维码失败: {resp.get('error')}"}
            except Exception as e:
                logger.error(f"Start Open QR Error: {e}")
                return {"state": False, "msg": str(e)}

    def poll_open_qrcode(self) -> Dict[str, Any]:
        """轮询 OpenID 扫码状态"""
        with self._lock:
            if not self._qr_token:
                return {"state": False, "msg": "QR not initialized"}

            if P115Client is None:
                return {"state": False, "msg": "p115client 未安装"}

            try:
                status_resp = P115Client.login_qrcode_scan_status(self._qr_token)
                status_code = status_resp.get("data", {}).get("status")

                if status_code == 2:
                    # 用户确认，获取 access_token
                    token_resp = P115Client.login_qrcode_access_token_open(
                        self._qr_token["uid"],
                        code_verifier=CODE_VERIFIER
                    )

                    if token_resp.get("code") == 0 and token_resp.get("data"):
                        data = token_resp["data"]
                        self._access_token = data["access_token"]
                        self._refresh_token = data["refresh_token"]
                        self._expires_at = time.time() + data.get("expires_in", 7200)
                        self.init_with_token(self._access_token)

                        return {
                            "state": True,
                            "status": "success",
                            "access_token": self._access_token,
                            "refresh_token": self._refresh_token,
                            "cookies": {
                                "access_token": self._access_token,
                                "refresh_token": self._refresh_token
                            },
                            "user": self.client.user_info().get("data", {}) if self.client else {}
                        }
                    else:
                        return {"state": False, "status": "error", "msg": f"换取 Token 失败: {token_resp.get('error')}"}

                status_map = {0: "waiting", 1: "scanned", 2: "success", -1: "expired", -2: "error"}
                return {"state": True, "status": status_map.get(status_code, "waiting")}

            except Exception as e:
                logger.error(f"Poll Open QR Error: {e}")
                return {"state": False, "status": "error", "msg": str(e)}

    def init_with_token(self, access_token: str) -> bool:
        """使用 access_token 初始化客户端"""
        try:
            if P115Client is None:
                return False
            cli = P115Client(access_token=access_token, check_for_relogin=True)
            ui = cli.user_info()
            if ui and ui.get("state"):
                self.client = cli
                return True
        except Exception as e:
            logger.error(f"Init Token Error: {e}")
        return False

    def refresh_access_token(self) -> Optional[str]:
        """刷新 access_token"""
        if not self._refresh_token or P115Client is None:
            return None
        try:
            resp = P115Client.login_refresh_token_open(self._refresh_token)
            if resp.get("code") == 0:
                data = resp["data"]
                self._access_token = data["access_token"]
                self._refresh_token = data["refresh_token"]
                self._expires_at = time.time() + data.get("expires_in", 7200)
                self.init_with_token(self._access_token)
                return self._access_token
        except Exception as e:
            logger.error(f"Refresh Token Error: {e}")
        return None

    def get_valid_client(self) -> Optional[P115Client]:
        """获取有效的客户端实例"""
        if self.client and time.time() < self._expires_at:
            return self.client
        if self._refresh_token and self.refresh_access_token():
            return self.client
        return None


class StandardClientHolder:
    """115 标准 (Cookie/扫码) 客户端持有者"""

    def __init__(self, secret_store=None):
        self.client: Optional[P115Client] = None
        self.cookies: Optional[str] = None
        self.user_info: Dict[str, Any] = {}
        self._qr_token: Optional[dict] = None
        self._lock = threading.RLock()
        self._secret_store = secret_store
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://115.com/"
        }

        # 尝试从持久化存储加载 Cookie
        self._load_from_store()

    def _load_from_store(self):
        """从 SecretStore 加载 Cookie"""
        if not self._secret_store:
            return
        try:
            for key in ['cloud115_qr_cookies', 'cloud115_manual_cookies', 'cloud115_cookies']:
                saved_cookies = self._secret_store.get_secret(key)
                if saved_cookies:
                    logger.info(f"从 {key} 加载 115 cookies (len: {len(saved_cookies)})")
                    if saved_cookies.startswith('{'):
                        cookies_dict = json.loads(saved_cookies)
                        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
                    else:
                        cookie_str = saved_cookies
                    self.init_with_cookie(cookie_str, save=False)
                    break
        except Exception as e:
            logger.warning(f"加载 115 cookies 失败: {e}")

    def _save_to_store(self, cookies_dict: dict):
        """保存 Cookie 到 SecretStore"""
        if self._secret_store and cookies_dict:
            try:
                self._secret_store.set_secret('cloud115_qr_cookies', json.dumps(cookies_dict))
                self._secret_store.set_secret('cloud115_cookies', json.dumps(cookies_dict))
                logger.info("已保存 115 cookies 到存储")
            except Exception as e:
                logger.error(f"保存 115 cookies 失败: {e}")

    def start_qrcode(self, app: str = "tv") -> dict:
        """获取扫码二维码"""
        with self._lock:
            if P115Client is None:
                return {"state": False, "msg": "p115client 未安装"}

            target_app = app if app in SUPPORTED_APPS else "tv"
            try:
                logger.info(f"[115 QR] 请求二维码 token for app: {target_app}")
                resp = P115Client.login_qrcode_token(app=target_app)
                logger.info(f"[115 QR] login_qrcode_token 响应: {resp}")

                if resp and resp.get("state"):
                    self._qr_token = resp["data"]
                    self._qr_token["app"] = target_app
                    uid = self._qr_token.get("uid")
                    logger.info(f"[115 QR] 获取 UID: {uid}")

                    # 下载二维码图片
                    try:
                        img_url = f"https://qrcodeapi.115.com/api/1.0/{target_app}/1.0/qrcode?uid={uid}"
                        logger.info(f"[115 QR] 下载二维码: {img_url}")
                        img_resp = requests.get(img_url, headers=self.headers, timeout=10)

                        if img_resp.status_code == 200:
                            b64_img = base64.b64encode(img_resp.content).decode('utf-8')
                            self._qr_token["qrcode"] = b64_img
                            logger.info(f"[115 QR] 二维码下载成功, 大小: {len(b64_img)} bytes")
                        else:
                            logger.error(f"[115 QR] 二维码下载失败, status: {img_resp.status_code}")
                            self._qr_token["qrcode"] = ""
                    except Exception as e:
                        logger.error(f"[115 QR] 二维码下载异常: {e}")
                        self._qr_token["qrcode"] = ""

                    return {
                        "state": True,
                        "uid": uid,
                        "time": self._qr_token.get("time"),
                        "sign": self._qr_token.get("sign"),
                        "qrcode": self._qr_token.get("qrcode", ""),
                        "app": target_app
                    }
                else:
                    error_msg = resp.get('message') if resp else "No response"
                    logger.error(f"[115 QR] 获取二维码失败: {error_msg}")
                    return {"state": False, "msg": f"获取二维码失败: {error_msg}"}
            except Exception as e:
                logger.error(f"[115 QR] start_qrcode 异常: {e}", exc_info=True)
                return {"state": False, "msg": str(e)}

    def poll_qrcode(self) -> dict:
        """轮询扫码状态"""
        with self._lock:
            if not self._qr_token:
                logger.warning("[115 QR] 轮询时没有 QR token")
                return {"state": False, "msg": "no token"}

            if P115Client is None:
                return {"state": False, "msg": "p115client 未安装"}

            try:
                target_app = self._qr_token.get("app") or "tv"
                status = P115Client.login_qrcode_scan_status(self._qr_token)
                data = status.get("data", {}) if isinstance(status, dict) else {}
                st = data.get("status")
                logger.debug(f"[115 QR] 扫码状态: {st}")

                if st == 2:
                    logger.info("[115 QR] 扫码成功，获取 cookie...")
                    result = P115Client.login_qrcode_scan_result(self._qr_token.get("uid"), app=target_app)
                    if result.get("state"):
                        cookie_obj = result["data"].get("cookie")
                        if isinstance(cookie_obj, dict):
                            cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_obj.items()])
                            cookies_dict = cookie_obj
                        else:
                            cookie_str = str(cookie_obj)
                            cookies_dict = {}

                        self.cookies = cookie_str
                        self.client = P115Client(cookies=cookie_str, check_for_relogin=True)

                        ui = self.client.user_info()
                        if ui and ui.get("state"):
                            self.user_info = ui["data"]

                        logger.info(f"[115 QR] 登录成功: {self.user_info.get('user_name', 'Unknown')}")
                        # 保存 Cookie
                        self._save_to_store(cookies_dict)
                        return {"state": True, "status": "success", "cookies": cookies_dict, "user": self.user_info}

                status_map = {0: "waiting", 1: "scanned", 2: "success", -1: "expired", -2: "error"}
                return {"state": True, "status": status_map.get(st, "waiting")}
            except Exception as e:
                logger.error(f"[115 QR] 轮询异常: {e}", exc_info=True)
                return {"state": False, "status": "error", "msg": str(e)}

    def init_with_cookie(self, cookies: str, save: bool = True) -> bool:
        """使用 Cookie 初始化客户端"""
        with self._lock:
            if P115Client is None:
                return False
            try:
                # 清洗 Cookie 字符串
                clean_cookies = cookies.replace("Cookie:", "").replace("\n", "").strip()
                cli = P115Client(cookies=clean_cookies, check_for_relogin=True)
                ui = cli.user_info()
                if ui and ui.get("state"):
                    self.client = cli
                    self.cookies = clean_cookies
                    self.user_info = ui["data"]
                    if save and self._secret_store:
                        # 将 cookie 字符串转为字典保存
                        cookies_dict = {}
                        for part in clean_cookies.split(';'):
                            if '=' in part:
                                k, v = part.strip().split('=', 1)
                                cookies_dict[k] = v
                        self._save_to_store(cookies_dict)
                    return True
            except Exception as e:
                logger.error(f"Init Cookie Error: {e}")
            return False

    def get_valid_client(self) -> Optional[P115Client]:
        """获取有效的客户端实例"""
        return self.client

    # ========== 文件操作方法 ==========

    def fs_files(self, cid=0, limit=1000):
        if not self.client:
            return {"state": False, "error": "not init"}
        try:
            return self.client.fs_files({"cid": cid, "limit": limit, "show_dir": 1})
        except Exception as e:
            return {"state": False, "error": str(e)}

    def fs_mkdir(self, pid, name):
        if not self.client:
            return {"state": False}
        return self.client.fs_mkdir(pid=pid, payload=name)

    def fs_rename(self, fid, new_name):
        if not self.client:
            return {"state": False}
        return self.client.fs_rename(payload=(fid, new_name))

    def fs_move(self, fids, to_cid):
        if not self.client:
            return {"state": False}
        return self.client.fs_move(payload=fids, pid=to_cid)

    def fs_delete(self, fids):
        if not self.client:
            return {"state": False}
        return self.client.fs_delete(fids)

    def offline_add_url(self, url, save_cid):
        if not self.client:
            return {"state": False}
        return self.client.offline_add_url(payload={"url": url, "wp_path_id": save_cid})

    def share_receive(self, share_code, receive_code, to_cid):
        """转存分享"""
        if not self.client:
            return {"state": False}
        payload = {"share_code": share_code, "receive_code": receive_code, "cid": to_cid, "file_id": "0", "is_check": 0}
        return self.client.share_receive(payload=payload)

    def get_user_info(self) -> Dict[str, Any]:
        with self._lock:
            if self.client:
                try:
                    res = self.client.user_info()
                    if res and res.get("state"):
                        self.user_info = res.get("data")
                except Exception as e:
                    logger.debug(f"获取用户信息失败: {e}")
            return self.user_info

    def get_storage_info(self) -> Dict[str, Any]:
        if not self.client:
            return {}
        try:
            res = self.client.fs_storage_info()
            return res.get("data") if res and res.get("state") else {}
        except Exception as e:
            logger.debug(f"获取存储信息失败: {e}")
            return {}

    def get_offline_quota(self) -> Dict[str, Any]:
        if not self.client:
            return {}
        try:
            res = self.client.offline_quota_info()
            return res.get("data") if res and res.get("state") else {}
        except Exception as e:
            logger.debug(f"获取离线配额失败: {e}")
            return {}


class P115Service:
    """115 网盘服务"""

    def __init__(self, secret_store=None):
        self._secret_store = secret_store
        self._standard_holder: Optional[StandardClientHolder] = None
        self._open_holder: Optional[OpenAppClientHolder] = None
        self._session_cache: Dict[str, dict] = {}
        self._lock = threading.RLock()

    def _ensure_standard_holder(self) -> StandardClientHolder:
        if not self._standard_holder:
            self._standard_holder = StandardClientHolder(self._secret_store)
        return self._standard_holder

    def _ensure_open_holder(self, client_id: str = "", client_secret: str = "") -> OpenAppClientHolder:
        if not self._open_holder or (client_id and self._open_holder.client_id != client_id):
            self._open_holder = OpenAppClientHolder(client_id, client_secret)
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

    def poll_login_status(self, session_id: str) -> Dict[str, Any]:
        """轮询登录状态"""
        session_info = self._session_cache.get(session_id)
        if not session_info:
            return {"success": False, "error": "Session not found", "status": "error"}

        login_method = session_info.get("login_method", "qrcode")

        if login_method == "open_app":
            holder = self._ensure_open_holder()
            result = holder.poll_open_qrcode()
        else:
            holder = self._ensure_standard_holder()
            result = holder.poll_qrcode()

        status = result.get("status", "waiting")

        if status == "success":
            return {
                "success": True,
                "status": "success",
                "cookies": result.get("cookies", {}),
                "user": result.get("user", {})
            }
        elif status == "expired":
            return {"success": False, "status": "expired", "error": "二维码已过期"}
        elif status == "error":
            return {"success": False, "status": "error", "error": result.get("msg", "轮询失败")}
        else:
            return {"success": True, "status": status}

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
                    formatted.append({
                        "id": str(f.get("fid") or f.get("cid")),
                        "name": f.get("n") or f.get("file_name"),
                        "size": f.get("s") or f.get("file_size", 0),
                        "is_directory": f.get("fc") == "folder" or f.get("ico") == "folder"
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
            result = holder.share_receive(share_code, access_code or "", int(save_cid))
            if result and result.get("state"):
                return {"success": True, "data": {"count": 1}}
            return {"success": False, "error": result.get("error", "转存失败")}
        except Exception as e:
            logger.error(f"转存分享失败: {e}")
            return {"success": False, "error": str(e)}


# 全局服务实例
_p115_service: Optional[P115Service] = None


def get_p115_service(secret_store=None) -> P115Service:
    """获取全局 P115Service 实例"""
    global _p115_service
    if _p115_service is None:
        _p115_service = P115Service(secret_store)
    return _p115_service


def init_p115_service(secret_store) -> P115Service:
    """初始化 P115Service 并设置全局实例"""
    global _p115_service
    _p115_service = P115Service(secret_store)
    return _p115_service