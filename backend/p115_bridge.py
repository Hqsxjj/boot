import base64
import logging
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

try:
    from p115client import P115Client, check_response
    from p115client.exception import P115Error, P115LoginError
except Exception:  # pragma: no cover - fallback when dependency is missing
    P115Client = None  # type: ignore
    check_response = None  # type: ignore

    class P115Error(Exception):
        """Fallback error type when p115client is unavailable."""

    class P115LoginError(P115Error):
        """Fallback login error when p115client is unavailable."""


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class P115BridgeError(RuntimeError):
    """Base exception for bridge failures."""


class P115BridgeDependencyError(P115BridgeError):
    """Raised when p115client is not installed or importable."""


class P115BridgeAuthenticationError(P115BridgeError):
    """Raised when authentication against 115 fails."""


class P115Bridge:
    """Higher-level helper around p115client with retries and data helpers."""

    def __init__(
        self,
        cookies: str,
        user_agent: Optional[str] = None,
        app: Optional[str] = None,
        *,
        max_retries: int = 2,
        retry_delay: float = 0.6,
        client: Optional[P115Client] = None,
    ):
        self._ensure_dependency()
        if not cookies:
            raise P115BridgeError("115 cookies are required")

        self.cookies = cookies.strip()
        self.user_agent = user_agent.strip() if user_agent else None
        self.app = (app or "web").strip()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.client = client or self._build_client()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def check_login(self) -> bool:
        """Return True if cookies are still valid."""
        return bool(self._with_retry(lambda: self.client.login_status()))

    def get_user_profile(self) -> Dict[str, Any]:
        """Return normalized user metadata."""
        resp = self._with_retry(lambda: check_response(self.client.user_info()))  # type: ignore[arg-type]
        data = self._as_dict(resp)
        profile = {
            "uid": data.get("user_id") or data.get("uid") or data.get("id"),
            "nickname": data.get("user_name")
            or data.get("nick_name")
            or data.get("nickname"),
            "avatar": data.get("avatar") or data.get("face") or data.get("face_url"),
            "vip": data.get("vip")
            or data.get("vip_level")
            or (data.get("vipinfo") or {}).get("level"),
            "space": data.get("space_info") or data.get("space") or {},
            "raw": data,
        }
        return profile

    def list_folders(self, cid: str = "0", *, limit: int = 200, offset: int = 0) -> Dict[str, Any]:
        payload = {
            "cid": cid,
            "limit": limit,
            "offset": offset,
            "show_dir": 1,
            "aid": 1,
        }
        resp = self._with_retry(lambda: check_response(self.client.fs_files(payload)))  # type: ignore[arg-type]
        entries = self._as_list(resp)
        return {
            "cid": cid,
            "items": [self._format_entry(item) for item in entries],
            "raw": resp,
        }

    def add_offline_tasks(self, urls: Iterable[str] | str, target_cid: Optional[str] = None) -> Dict[str, Any]:
        if isinstance(urls, str):
            payload: Dict[str, Any] = {"urls": urls.strip()}
        else:
            payload = {"urls": "\n".join(u.strip() for u in urls if u.strip())}
        if not payload["urls"]:
            raise P115BridgeError("At least one URL is required")
        if target_cid:
            payload["wp_path_id"] = target_cid
        resp = self._with_retry(lambda: check_response(self.client.offline_add_urls(payload)))  # type: ignore[arg-type]
        return resp

    def list_offline_tasks(self, page: int = 1) -> Dict[str, Any]:
        resp = self._with_retry(lambda: check_response(self.client.offline_list({"page": page})))  # type: ignore[arg-type]
        return resp

    # ------------------------------------------------------------------
    # QR helpers
    # ------------------------------------------------------------------
    @classmethod
    def request_qr_token(cls, app: str = "web") -> Dict[str, Any]:
        cls._ensure_dependency()
        resp = check_response(P115Client.login_qrcode_token(app=app))  # type: ignore[arg-type]
        return cls._as_dict(resp)

    @classmethod
    def fetch_qr_image(cls, token_payload: Dict[str, Any], app: str = "web") -> bytes:
        cls._ensure_dependency()
        if not token_payload:
            raise P115BridgeError("Token payload is required")
        uid = token_payload.get("uid")
        if not uid:
            raise P115BridgeError("Token payload must include uid")
        return P115Client.login_qrcode(token_payload, app=app)  # type: ignore[arg-type]

    @classmethod
    def qr_status(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        cls._ensure_dependency()
        if not payload:
            raise P115BridgeError("QR payload is required")
        resp = check_response(P115Client.login_qrcode_scan_status(payload))  # type: ignore[arg-type]
        return cls._as_dict(resp)

    @classmethod
    def complete_qr_login(cls, uid: str, app: str = "web") -> Dict[str, Any]:
        cls._ensure_dependency()
        if not uid:
            raise P115BridgeError("UID is required to finalize QR login")
        resp = check_response(P115Client.login_qrcode_scan_result(uid, app=app))  # type: ignore[arg-type]
        data = cls._as_dict(resp)
        cookie = ((data.get("data") or data).get("cookie") if isinstance(data.get("data"), dict) else data.get("cookie"))
        if not cookie:
            raise P115BridgeError("QR login response did not include cookie data")
        return data

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_client(self) -> P115Client:
        client = P115Client(cookies=self.cookies, app=self.app, console_qrcode=False)  # type: ignore[call-arg]
        if self.user_agent:
            client.headers["user-agent"] = self.user_agent
        return client

    def _with_retry(self, func: Callable[[], Any]) -> Any:
        attempt = 0
        while True:
            try:
                return func()
            except P115LoginError as exc:  # type: ignore[arg-type]
                logger.warning("115 login expired: %s", exc)
                raise P115BridgeAuthenticationError("115 authentication failed") from exc
            except P115Error as exc:  # type: ignore[arg-type]
                attempt += 1
                if attempt > self.max_retries:
                    logger.exception("115 API call failed after retries")
                    raise P115BridgeError(str(exc)) from exc
                time.sleep(self.retry_delay * attempt)
            except Exception as exc:  # pragma: no cover - defensive
                attempt += 1
                if attempt > self.max_retries:
                    logger.exception("Unexpected 115 error")
                    raise P115BridgeError(str(exc)) from exc
                time.sleep(self.retry_delay * attempt)

    @staticmethod
    def _as_dict(resp: Any) -> Dict[str, Any]:
        if isinstance(resp, dict):
            return resp
        return {"data": resp}

    @staticmethod
    def _as_list(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
        if isinstance(resp, list):
            return resp
        if not isinstance(resp, dict):
            return []
        for key in ("data", "list", "files", "file_list"):
            value = resp.get(key)
            if isinstance(value, list):
                return value
        return []

    @staticmethod
    def _format_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        entry_id = entry.get("cid") or entry.get("file_id") or entry.get("id")
        parent_id = entry.get("pid") or entry.get("parent_id") or entry.get("cid")
        name = entry.get("n") or entry.get("name") or entry.get("file_name") or ""
        is_dir_flags = (
            entry.get("is_dir"),
            entry.get("is_directory"),
            entry.get("file_category") == 0,
            entry.get("category") == 0,
            entry.get("mime") == "application/x-directory",
        )
        is_dir = any(flag for flag in is_dir_flags if flag is not None)
        size = entry.get("size") or entry.get("file_size") or 0
        updated = (
            entry.get("updated_at")
            or entry.get("update_time")
            or entry.get("mtime")
            or entry.get("time")
            or entry.get("last_update_time")
        )
        return {
            "id": str(entry_id) if entry_id is not None else None,
            "parentId": str(parent_id) if parent_id is not None else None,
            "name": name,
            "isDirectory": bool(is_dir),
            "size": size,
            "updatedAt": updated,
            "raw": entry,
        }

    @staticmethod
    def _ensure_dependency():
        if P115Client is None or check_response is None:
            raise P115BridgeDependencyError(
                "p115client is not installed. Install it from https://github.com/poolzier/p115client"
            )


def encode_qr_image(png_bytes: bytes) -> str:
    """Return a data URI for a QR png response."""
    if not png_bytes:
        return ""
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("utf-8")

