"""
p115_open_client.py - 115 开放平台原生客户端

基于 EmbyNginxDK 项目重构，使用原生 requests 实现
特点：
- PKCE sha256 认证流程
- Token 自动刷新和持久化
- 完整文件操作 API
- 无第三方 115 库依赖
"""

import os
import json
import time
import base64
import hashlib
import secrets
import logging
import threading
import requests
from typing import Optional, Dict, Any, Tuple, Union, Callable
from datetime import datetime
from hashlib import sha1

logger = logging.getLogger(__name__)

# 线程锁
_token_lock = threading.Lock()


class P115OpenClient:
    """
    115 开放平台客户端 - 原生 requests 实现
    
    支持:
    - PKCE (sha256) 二维码登录
    - Token 自动刷新
    - 文件列表/下载/上传
    """
    
    BASE_URL = "https://proapi.115.com"
    PASSPORT_URL = "https://passportapi.115.com"
    QRCODE_URL = "https://qrcodeapi.115.com"
    
    def __init__(
        self,
        access_token: str = None,
        refresh_token: str = None,
        expires_in: int = 0,
        refresh_time: int = 0,
        token_service = None,
        app_id: str = None
    ):
        """
        初始化客户端
        
        Args:
            access_token: 访问令牌
            refresh_token: 刷新令牌
            expires_in: 过期时间（秒）
            refresh_time: 上次刷新时间戳
            token_service: 数据库 Token 服务
            app_id: 第三方应用 ID
        """
        self.session = requests.Session()
        self._init_session()
        
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_in = expires_in
        self._refresh_time = refresh_time
        self._token_service = token_service
        self._app_id = app_id
        self._user_info: Dict[str, Any] = {}
        
        # 二维码登录相关
        self._qr_token: Optional[Dict] = None
        self._code_verifier: Optional[str] = None
    
    def _init_session(self):
        """初始化 HTTP 会话"""
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/x-www-form-urlencoded"
        })
    
    # ========== PKCE 认证 ==========
    
    def generate_qrcode(self, app_id: str = None) -> Dict[str, Any]:
        """
        生成带 PKCE (sha256) 的授权二维码
        
        Args:
            app_id: 第三方应用 ID，默认使用初始化时的值或公共 ID
            
        Returns:
            包含 qrcode_url, uid, time, sign, code_verifier 的字典
        """
        if app_id:
            self._app_id = app_id
        if not self._app_id:
            self._app_id = "100197531"  # 默认公共 App ID
        
        # 生成 PKCE 参数
        self._code_verifier = secrets.token_urlsafe(96)[:128]
        code_challenge = base64.b64encode(
            hashlib.sha256(self._code_verifier.encode("utf-8")).digest()
        ).decode("utf-8")
        
        try:
            resp = self.session.post(
                f"{self.PASSPORT_URL}/open/authDeviceCode",
                data={
                    "client_id": self._app_id,
                    "code_challenge": code_challenge,
                    "code_challenge_method": "sha256"
                },
                timeout=10
            )
            result = resp.json()
            
            if result.get("code") != 0:
                error_msg = result.get("message", "获取二维码失败")
                logger.warning(f"[115 Open] 获取二维码失败: {error_msg}")
                return {"success": False, "error": error_msg}
            
            data = result["data"]
            self._qr_token = {
                "uid": data["uid"],
                "time": str(data["time"]),
                "sign": data["sign"]
            }
            
            # 下载二维码图片并转 base64
            qrcode_b64 = ""
            try:
                img_resp = self.session.get(data["qrcode"], timeout=10)
                if img_resp.status_code == 200:
                    raw_b64 = base64.b64encode(img_resp.content).decode("utf-8")
                    content_type = img_resp.headers.get("content-type", "image/png")
                    mime = content_type.split(";")[0] if content_type else "image/png"
                    qrcode_b64 = f"data:{mime};base64,{raw_b64}"
            except Exception as e:
                logger.warning(f"[115 Open] 下载二维码图片失败: {e}")
            
            return {
                "success": True,
                "qrcode": qrcode_b64,
                "qrcode_url": data["qrcode"],
                "uid": data["uid"],
                "time": str(data["time"]),
                "sign": data["sign"],
                "code_verifier": self._code_verifier
            }
            
        except Exception as e:
            logger.error(f"[115 Open] generate_qrcode 异常: {e}")
            return {"success": False, "error": str(e)}
    
    def poll_qrcode_status(self) -> Dict[str, Any]:
        """
        轮询二维码扫码状态
        
        Returns:
            状态字典，status 可选值: waiting, scanned, success, expired, error
        """
        if not self._qr_token:
            return {"success": False, "status": "error", "error": "未初始化二维码"}
        
        try:
            resp = self.session.get(
                f"{self.QRCODE_URL}/get/status/",
                params={
                    "uid": self._qr_token["uid"],
                    "time": int(self._qr_token["time"]),
                    "sign": self._qr_token["sign"]
                },
                timeout=10
            )
            result = resp.json()
            
            if not result.get("data"):
                return {"success": True, "status": "expired"}
            
            status_code = result["data"].get("status", 0)
            status_map = {0: "waiting", 1: "scanned", 2: "success", -1: "expired", -2: "error"}
            status = status_map.get(status_code, "waiting")
            
            if status_code == 2:
                # 扫码成功，获取 Token
                token_result = self._get_access_token(
                    self._qr_token["uid"],
                    self._code_verifier
                )
                if token_result.get("success"):
                    return {
                        "success": True,
                        "status": "success",
                        "access_token": self._access_token,
                        "refresh_token": self._refresh_token,
                        "user": self._user_info
                    }
                else:
                    return {"success": False, "status": "error", "error": token_result.get("error")}
            
            return {"success": True, "status": status}
            
        except Exception as e:
            logger.error(f"[115 Open] poll_qrcode_status 异常: {e}")
            return {"success": False, "status": "error", "error": str(e)}
    
    def _get_access_token(self, uid: str, code_verifier: str) -> Dict[str, Any]:
        """扫码成功后换取 access_token"""
        try:
            resp = self.session.post(
                f"{self.PASSPORT_URL}/open/deviceCodeToToken",
                data={
                    "uid": uid,
                    "code_verifier": code_verifier
                },
                timeout=10
            )
            result = resp.json()
            
            if result.get("code") != 0:
                error_msg = result.get("message", "获取 Token 失败")
                return {"success": False, "error": error_msg}
            
            data = result["data"]
            self._access_token = data["access_token"]
            self._refresh_token = data["refresh_token"]
            self._expires_in = data.get("expires_in", 7200)
            self._refresh_time = int(time.time())
            
            # 获取用户信息
            self._fetch_user_info()
            
            # 持久化保存
            self._save_token()
            
            logger.info(f"[115 Open] 登录成功: {self._user_info.get('user_name', 'Unknown')}")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"[115 Open] _get_access_token 异常: {e}")
            return {"success": False, "error": str(e)}
    
    def refresh_access_token(self) -> bool:
        """刷新 access_token"""
        if not self._refresh_token:
            return False
        
        with _token_lock:
            try:
                resp = self.session.post(
                    f"{self.PASSPORT_URL}/open/refreshToken",
                    data={"refresh_token": self._refresh_token},
                    timeout=10
                )
                result = resp.json()
                
                if result.get("code") != 0:
                    logger.warning(f"[115 Open] 刷新 Token 失败: {result.get('message')}")
                    return False
                
                data = result["data"]
                self._access_token = data["access_token"]
                self._refresh_token = data["refresh_token"]
                self._expires_in = data.get("expires_in", 7200)
                self._refresh_time = int(time.time())
                
                # 持久化保存
                self._save_token()
                
                logger.info("[115 Open] Token 刷新成功")
                return True
                
            except Exception as e:
                logger.error(f"[115 Open] refresh_access_token 异常: {e}")
                return False
    
    def _save_token(self):
        """保存 Token 到数据库"""
        if not self._token_service:
            return
        try:
            expires_at = datetime.fromtimestamp(self._refresh_time + self._expires_in)
            name = f"open_{self._user_info.get('user_name', 'default')}"
            self._token_service.save_open_token(
                name=name,
                access_token=self._access_token,
                refresh_token=self._refresh_token,
                expires_at=expires_at,
                app_id=self._app_id,
                user_id=str(self._user_info.get("user_id", "")),
                user_name=self._user_info.get("user_name")
            )
        except Exception as e:
            logger.error(f"[115 Open] 保存 Token 失败: {e}")
    
    @property
    def access_token(self) -> Optional[str]:
        """获取有效的 access_token，过期自动刷新"""
        if not self._access_token:
            return None
        
        # 检查是否需要刷新（提前 60 秒刷新）
        if self._refresh_time and self._expires_in:
            if self._refresh_time + self._expires_in < int(time.time()) + 60:
                self.refresh_access_token()
        
        if self._access_token:
            self.session.headers.update({"Authorization": f"Bearer {self._access_token}"})
        
        return self._access_token
    
    @property
    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return bool(self.access_token)
    
    # ========== API 请求 ==========
    
    def _request(
        self,
        method: str,
        endpoint: str,
        result_key: str = None,
        **kwargs
    ) -> Optional[Union[Dict, list]]:
        """
        通用 API 请求方法
        
        Args:
            method: HTTP 方法
            endpoint: API 端点
            result_key: 返回数据的键名
            **kwargs: 传递给 requests 的参数
            
        Returns:
            API 响应数据
        """
        if not self.access_token:
            raise Exception("未登录")
        
        try:
            resp = self.session.request(
                method,
                f"{self.BASE_URL}{endpoint}",
                timeout=30,
                **kwargs
            )
            
            # 处理速率限制
            if resp.status_code == 429:
                reset_time = int(resp.headers.get("X-RateLimit-Reset", 60))
                logger.warning(f"[115 Open] 触发速率限制，等待 {reset_time} 秒")
                time.sleep(reset_time + 5)
                return self._request(method, endpoint, result_key, **kwargs)
            
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") != 0:
                logger.warning(f"[115 Open] API 错误: {result.get('message')}")
            
            if result_key:
                return result.get(result_key)
            return result
            
        except Exception as e:
            logger.error(f"[115 Open] API 请求失败: {e}")
            raise
    
    # ========== 用户信息 ==========
    
    def _fetch_user_info(self):
        """获取用户信息"""
        try:
            resp = self._request("GET", "/open/user/info", "data")
            if resp:
                self._user_info = {
                    "user_id": resp.get("user_id"),
                    "user_name": resp.get("user_name")
                }
        except:
            pass
    
    def user_info(self) -> Dict[str, Any]:
        """获取用户信息"""
        if not self._user_info:
            self._fetch_user_info()
        return self._user_info
    
    # ========== 文件操作 ==========
    
    def get_item(self, path: str = None, file_id: int = None) -> Optional[Dict]:
        """
        获取文件/目录信息
        
        Args:
            path: 文件路径
            file_id: 文件 ID
            
        Returns:
            文件信息字典
        """
        try:
            if path:
                if not path.startswith("/"):
                    path = "/" + path
                return self._request("POST", "/open/folder/get_info", "data", data={"path": path})
            elif file_id:
                return self._request("GET", "/open/folder/get_info", "data", params={"file_id": int(file_id)})
            return None
        except:
            return None
    
    def list_directory(self, cid: int = 0, limit: int = 1000) -> Optional[Dict]:
        """
        列出目录内容
        
        Args:
            cid: 目录 ID，0 表示根目录
            limit: 返回数量限制
            
        Returns:
            包含文件列表的字典
        """
        try:
            return self._request(
                "GET",
                "/open/ufile/files",
                "data",
                params={"cid": cid, "limit": limit, "show_dir": 1}
            )
        except:
            return None
    
    def download_url(self, pick_code: str, user_agent: str = None) -> Optional[str]:
        """
        获取下载链接
        
        Args:
            pick_code: 文件的 pick_code
            user_agent: 自定义 User-Agent
            
        Returns:
            下载 URL
        """
        try:
            if user_agent:
                self.session.headers.update({"User-Agent": user_agent})
            
            result = self._request(
                "POST",
                "/open/ufile/downurl",
                "data",
                data={"pick_code": pick_code}
            )
            
            if result:
                # 返回第一个文件的下载链接
                first_file = list(result.values())[0] if result else {}
                return first_file.get("url", {}).get("url")
            return None
        except:
            return None
    
    def delete(self, file_id: int) -> bool:
        """删除文件/目录"""
        try:
            self._request("POST", "/open/ufile/delete", data={"file_ids": int(file_id)})
            return True
        except:
            return False
    
    def rename(self, file_id: int, new_name: str) -> bool:
        """重命名文件/目录"""
        try:
            result = self._request(
                "POST",
                "/open/ufile/update",
                data={"file_id": int(file_id), "file_name": new_name}
            )
            return result.get("state", False) if result else False
        except:
            return False
    
    def move(self, file_id: int, target_cid: int) -> bool:
        """移动文件/目录"""
        try:
            self._request(
                "POST",
                "/open/ufile/move",
                data={"file_ids": int(file_id), "pid": int(target_cid)}
            )
            return True
        except:
            return False
    
    def copy(self, file_id: int, target_cid: int) -> Optional[Dict]:
        """复制文件/目录"""
        try:
            result = self._request(
                "POST",
                "/open/ufile/copy",
                data={"file_id": int(file_id), "pid": int(target_cid)}
            )
            return result if result and result.get("state") else None
        except:
            return None
    
    def mkdir(self, parent_id: int, name: str) -> Optional[Dict]:
        """创建目录"""
        try:
            return self._request(
                "POST",
                "/open/folder/add",
                "data",
                data={"pid": int(parent_id), "file_name": name}
            )
        except:
            return None
    
    # ========== 上传 ==========
    
    def upload_file_init(
        self,
        filename: str,
        filesize: int,
        filesha1: str,
        read_range_bytes_or_hash: Callable = None,
        pid: int = 0
    ) -> Dict:
        """
        初始化上传（支持秒传）
        
        Args:
            filename: 文件名
            filesize: 文件大小
            filesha1: 文件 SHA1
            read_range_bytes_or_hash: 范围读取函数（大文件需要）
            pid: 目标目录 ID
            
        Returns:
            上传初始化结果
        """
        payload = {
            "file_name": filename,
            "fileid": filesha1.upper(),
            "file_size": filesize,
            "target": f"U_1_{pid}",
            "topupload": 1
        }
        
        try:
            result = self._request("POST", "/open/upload/init", data=payload)
            
            if not result or not result.get("state"):
                return result or {}
            
            data = result.get("data", {})
            
            # 需要二次验证
            if data.get("status") == 7:
                if read_range_bytes_or_hash is None:
                    raise ValueError("文件 >= 1MB 需要提供 read_range_bytes_or_hash")
                
                payload["sign_key"] = data["sign_key"]
                sign_check = data["sign_check"]
                content = read_range_bytes_or_hash(sign_check)
                
                if isinstance(content, str):
                    payload["sign_val"] = content.upper()
                else:
                    payload["sign_val"] = sha1(content).hexdigest().upper()
                
                result = self._request("POST", "/open/upload/init", data=payload)
            
            if result:
                result["reuse"] = result.get("data", {}).get("status") == 2
            return result.get("data", {})
            
        except Exception as e:
            logger.error(f"[115 Open] upload_file_init 失败: {e}")
            return {}


class P115CookieClient:
    """
    115 Cookie 客户端 - 原生 requests 实现
    
    支持:
    - 标准 QR 码登录（返回 Cookie）
    - Cookie 手动初始化
    - 文件操作 API
    """
    
    BASE_URL = "https://webapi.115.com"
    WEB_URL = "https://115.com"
    QRCODE_URL = "https://qrcodeapi.115.com"
    PASSPORT_URL = "https://passportapi.115.com"
    
    # 支持的登录客户端
    SUPPORTED_APPS = ["tv", "android", "ios", "ipad", "web", "desktop", "harmony", "qandroid"]
    
    def __init__(self, cookies: str = None, token_service=None):
        """
        初始化客户端
        
        Args:
            cookies: Cookie 字符串
            token_service: 数据库 Token 服务
        """
        self.session = requests.Session()
        self._init_session()
        
        self._cookies = cookies
        self._token_service = token_service
        self._user_info: Dict[str, Any] = {}
        
        # 二维码登录相关
        self._qr_token: Optional[Dict] = None
        self._target_app: str = "tv"
        
        # 如果有 Cookie，初始化
        if cookies:
            self._apply_cookies(cookies)
    
    def _init_session(self):
        """初始化 HTTP 会话"""
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://115.com/"
        })
    
    def _apply_cookies(self, cookies: str):
        """应用 Cookie 到会话"""
        self._cookies = cookies.replace("Cookie:", "").replace("\n", "").strip()
        for item in self._cookies.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                self.session.cookies.set(key, value)
    
    # ========== QR 码登录 ==========
    
    def generate_qrcode(self, app: str = "tv") -> Dict[str, Any]:
        """
        生成普通 QR 码（Cookie 登录）
        
        Args:
            app: 登录客户端类型
            
        Returns:
            包含 qrcode, uid, time, sign 的字典
        """
        self._target_app = app if app in self.SUPPORTED_APPS else "tv"
        
        try:
            resp = self.session.get(
                f"{self.QRCODE_URL}/api/1.0/{self._target_app}/1.0/token",
                timeout=10
            )
            result = resp.json()
            
            if not result.get("state"):
                return {"success": False, "error": result.get("message", "获取二维码失败")}
            
            data = result["data"]
            self._qr_token = {
                "uid": data["uid"],
                "time": str(data["time"]),
                "sign": data["sign"],
                "app": self._target_app
            }
            
            # 下载二维码图片
            uid = data["uid"]
            qrcode_b64 = ""
            try:
                img_url = f"https://qrcodeapi.115.com/api/1.0/{self._target_app}/1.0/qrcode?uid={uid}"
                img_resp = self.session.get(img_url, timeout=10)
                if img_resp.status_code == 200:
                    raw_b64 = base64.b64encode(img_resp.content).decode("utf-8")
                    content_type = img_resp.headers.get("content-type", "image/png")
                    mime = content_type.split(";")[0] if content_type else "image/png"
                    qrcode_b64 = f"data:{mime};base64,{raw_b64}"
            except Exception as e:
                logger.warning(f"[115 Cookie] 下载二维码图片失败: {e}")
            
            return {
                "success": True,
                "qrcode": qrcode_b64,
                "uid": data["uid"],
                "time": str(data["time"]),
                "sign": data["sign"],
                "app": self._target_app
            }
            
        except Exception as e:
            logger.error(f"[115 Cookie] generate_qrcode 异常: {e}")
            return {"success": False, "error": str(e)}
    
    def poll_qrcode_status(self, qr_token: Dict = None) -> Dict[str, Any]:
        """
        轮询 QR 码扫码状态
        
        Args:
            qr_token: 可选的外部 token，不传则使用内部保存的
            
        Returns:
            状态字典
        """
        token = qr_token or self._qr_token
        if not token or not token.get("uid"):
            return {"success": False, "status": "error", "error": "未初始化二维码"}
        
        try:
            resp = self.session.get(
                f"{self.QRCODE_URL}/get/status/",
                params={
                    "uid": token["uid"],
                    "time": int(token["time"]),
                    "sign": token["sign"]
                },
                timeout=10
            )
            result = resp.json()
            
            # state=0 表示 API 请求失败
            if result.get("state") == 0:
                code = result.get("code")
                if code == 40199002:
                    return {"success": True, "status": "expired"}
                return {"success": False, "status": "error", "error": result.get("message")}
            
            if not result.get("data"):
                return {"success": True, "status": "expired"}
            
            status_code = result["data"].get("status", 0)
            status_map = {0: "waiting", 1: "scanned", 2: "success", -1: "expired", -2: "error"}
            status = status_map.get(status_code, "waiting")
            
            if status_code == 2:
                # 扫码成功，获取 Cookie
                target_app = token.get("app", self._target_app)
                cookie_result = self._get_login_result(token["uid"], target_app)
                
                if cookie_result.get("success"):
                    return {
                        "success": True,
                        "status": "success",
                        "cookies": cookie_result.get("cookies"),
                        "user": self._user_info
                    }
                else:
                    return {"success": False, "status": "error", "error": cookie_result.get("error")}
            
            return {"success": True, "status": status}
            
        except Exception as e:
            logger.error(f"[115 Cookie] poll_qrcode_status 异常: {e}")
            return {"success": False, "status": "error", "error": str(e)}
    
    def _get_login_result(self, uid: str, app: str) -> Dict[str, Any]:
        """扫码成功后获取 Cookie"""
        try:
            resp = self.session.get(
                f"{self.QRCODE_URL}/api/2.0/{app}/1.0/login",
                params={"uid": uid},
                timeout=10
            )
            result = resp.json()
            
            if not result.get("state"):
                return {"success": False, "error": result.get("message", "获取 Cookie 失败")}
            
            cookie_data = result["data"].get("cookie", {})
            if isinstance(cookie_data, dict):
                cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_data.items()])
                cookies_dict = cookie_data
            else:
                cookie_str = str(cookie_data)
                cookies_dict = {}
            
            self._cookies = cookie_str
            self._apply_cookies(cookie_str)
            
            # 获取用户信息
            self._fetch_user_info()
            
            # 保存到数据库
            self._save_cookie(cookies_dict, app)
            
            logger.info(f"[115 Cookie] 登录成功: {self._user_info.get('user_name', 'Unknown')}")
            return {"success": True, "cookies": cookies_dict}
            
        except Exception as e:
            logger.error(f"[115 Cookie] _get_login_result 异常: {e}")
            return {"success": False, "error": str(e)}
    
    def _save_cookie(self, cookies_dict: Dict, app: str = None):
        """保存 Cookie 到数据库"""
        if not self._token_service or not cookies_dict:
            return
        try:
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
            user_id = self._user_info.get("user_id")
            user_name = self._user_info.get("user_name", "default")
            name = f"cookie_{user_name}"
            self._token_service.save_cookie_token(
                name=name,
                cookie=cookie_str,
                client=app,
                user_id=str(user_id) if user_id else None,
                user_name=user_name
            )
        except Exception as e:
            logger.error(f"[115 Cookie] 保存 Cookie 失败: {e}")
    
    # ========== 用户信息 ==========
    
    def _fetch_user_info(self):
        """获取用户信息"""
        try:
            resp = self.session.get(f"{self.BASE_URL}/?ct=ajax&ac=nav", timeout=10)
            result = resp.json()
            if result.get("state"):
                data = result.get("data", {})
                self._user_info = {
                    "user_id": data.get("user_id"),
                    "user_name": data.get("user_name")
                }
        except:
            pass
    
    def user_info(self) -> Dict[str, Any]:
        """获取用户信息"""
        if not self._user_info:
            self._fetch_user_info()
        return self._user_info
    
    @property
    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return bool(self._cookies)
    
    # ========== 文件操作 ==========
    
    def list_directory(self, cid: int = 0, limit: int = 1000) -> Optional[Dict]:
        """列出目录内容"""
        if not self._cookies:
            return None
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/files",
                params={"cid": cid, "limit": limit, "show_dir": 1, "aid": 1},
                timeout=30
            )
            return resp.json()
        except:
            return None
    
    def share_snap(self, params: Dict[str, Any]) -> Optional[Dict]:
        """
        获取分享链接的文件列表
        
        Args:
            params: 包含以下键的字典:
                - share_code: 分享码
                - receive_code: 提取码 (可选)
                - cid: 文件夹ID，默认 '0' 表示根目录
                - offset: 起始偏移，默认 0
                - limit: 返回数量，默认 20
        
        Returns:
            API 响应字典
        """
        if not self._cookies:
            return {"state": False, "error": "未登录"}
        
        share_code = params.get("share_code", "")
        receive_code = params.get("receive_code", "")
        cid = params.get("cid", "0")
        offset = params.get("offset", 0)
        limit = params.get("limit", 20)
        
        if not share_code:
            return {"state": False, "error": "share_code 不能为空"}
        
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/share/snap",
                params={
                    "share_code": share_code,
                    "receive_code": receive_code,
                    "cid": cid,
                    "offset": offset,
                    "limit": limit
                },
                timeout=30
            )
            result = resp.json()
            
            # 115 API 返回 state: true 表示成功
            if result.get("state"):
                return result
            else:
                return {
                    "state": False,
                    "error": result.get("error", "获取分享文件失败")
                }
        except Exception as e:
            logger.error(f"[P115CookieClient] share_snap 失败: {e}")
            return {"state": False, "error": str(e)}
    
    def download_url(self, pick_code: str) -> Optional[str]:
        """获取下载链接"""
        if not self._cookies:
            return None
        try:
            resp = self.session.post(
                f"{self.BASE_URL}/files/download",
                data={"pickcode": pick_code},
                timeout=30
            )
            result = resp.json()
            return result.get("file_url")
        except:
            return None
    
    def share_receive(self, share_code: str, receive_code: str = "", to_cid: int = 0, file_ids: list = None) -> Dict[str, Any]:
        """
        转存分享链接中的文件到指定目录
        
        Args:
            share_code: 分享码
            receive_code: 提取码 (可选)
            to_cid: 目标目录 ID，默认 0 表示根目录
            file_ids: 可选的文件 ID 列表，如果提供则只转存这些文件
        
        Returns:
            API 响应字典 {"state": True/False, ...}
        """
        if not self._cookies:
            return {"state": False, "error": "未登录"}
        
        if not share_code:
            return {"state": False, "error": "share_code 不能为空"}
        
        try:
            # 115 分享转存接口
            data = {
                "share_code": share_code,
                "receive_code": receive_code,
                "cid": to_cid
            }
            
            # 支持指定文件 ID 进行部分转存
            if file_ids:
                if isinstance(file_ids, list):
                    data["file_id"] = ",".join(str(fid) for fid in file_ids)
                else:
                    data["file_id"] = str(file_ids)
            
            resp = self.session.post(
                f"{self.BASE_URL}/share/receive",
                data=data,
                timeout=60  # 转存可能需要更长时间
            )
            result = resp.json()
            
            if result.get("state"):
                return {"state": True, "data": result.get("data", {})}
            else:
                return {
                    "state": False, 
                    "error": result.get("error", result.get("error_msg", "转存失败"))
                }
        except Exception as e:
            logger.error(f"[P115CookieClient] share_receive 失败: {e}")
            return {"state": False, "error": str(e)}


# ========== 工厂函数 ==========

def create_open_client(token_service=None) -> Optional[P115OpenClient]:
    """
    创建 115 Open 客户端，自动从数据库加载 Token
    
    Args:
        token_service: 数据库 Token 服务
        
    Returns:
        已初始化的客户端实例
    """
    if not token_service:
        return P115OpenClient()
    
    try:
        token_data = token_service.get_active_open_token()
        if token_data:
            expires_at_str = token_data.get("expiresAt")
            refresh_time = 0
            expires_in = 7200
            
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                refresh_time = int(expires_at.timestamp()) - 7200
                expires_in = 7200
            
            client = P115OpenClient(
                access_token=token_data.get("accessToken"),
                refresh_token=token_data.get("refreshToken"),
                expires_in=expires_in,
                refresh_time=refresh_time,
                token_service=token_service,
                app_id=token_data.get("appId")
            )
            logger.info(f"[115 Open] 从数据库加载 Token: {token_data.get('name')}")
            return client
    except Exception as e:
        logger.warning(f"[115 Open] 加载 Token 失败: {e}")
    
    return P115OpenClient(token_service=token_service)


def create_cookie_client(token_service=None) -> Optional[P115CookieClient]:
    """
    创建 115 Cookie 客户端，自动从数据库加载 Cookie
    
    Args:
        token_service: 数据库 Token 服务
        
    Returns:
        已初始化的客户端实例
    """
    if not token_service:
        return P115CookieClient()
    
    try:
        token_data = token_service.get_active_cookie_token()
        if token_data:
            cookie_str = token_data.get("cookie", "")
            if cookie_str:
                client = P115CookieClient(cookies=cookie_str, token_service=token_service)
                logger.info(f"[115 Cookie] 从数据库加载: {token_data.get('name')}")
                return client
    except Exception as e:
        logger.warning(f"[115 Cookie] 加载 Cookie 失败: {e}")
    
    return P115CookieClient(token_service=token_service)

