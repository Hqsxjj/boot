from __future__ import annotations

import time
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from middleware.auth import require_auth
from persistence.store import DataStore
from p115_bridge import (
    P115Bridge,
    P115BridgeAuthenticationError,
    P115BridgeDependencyError,
    P115BridgeError,
    encode_qr_image,
)

p115_bp = Blueprint("p115", __name__, url_prefix="/api/115")


def init_p115_blueprint(store: DataStore):
    p115_bp.store = store  # type: ignore[attr-defined]
    return p115_bp


@p115_bp.route("/login", methods=["POST"])
@require_auth
def login_cookie():
    data = request.get_json(silent=True) or {}
    cookies = data.get("cookies") or data.get("cookie")
    user_agent = data.get("userAgent") or data.get("user_agent")
    login_app = data.get("loginApp") or data.get("app") or "web"

    if not cookies:
        return _error("Cookies are required to authenticate with 115"), 400

    try:
        bridge = P115Bridge(cookies=cookies, user_agent=user_agent, app=login_app)
        profile = bridge.get_user_profile()
        bridge.check_login()
        _persist_cloud115({
            "cookies": cookies,
            "userAgent": user_agent or _cloud_config().get("userAgent", ""),
            "loginApp": login_app,
            "loginMethod": "cookie",
        })
    except P115BridgeDependencyError as exc:
        return _error(str(exc)), 503
    except P115BridgeAuthenticationError as exc:
        return _error(str(exc)), 401
    except P115BridgeError as exc:
        return _error(str(exc)), 400

    return jsonify({
        "success": True,
        "data": {
            "profile": profile,
            "loginMethod": "cookie",
        },
    })


@p115_bp.route("/login/qr/start", methods=["POST"])
@require_auth
def start_qr_login():
    data = request.get_json(silent=True) or {}
    app = data.get("app") or "web"
    try:
        token_resp = P115Bridge.request_qr_token(app=app)
        token_payload = token_resp.get("data") if isinstance(token_resp.get("data"), dict) else token_resp
        qr_png = P115Bridge.fetch_qr_image(token_payload, app=app)
    except P115BridgeDependencyError as exc:
        return _error(str(exc)), 503
    except P115BridgeError as exc:
        return _error(str(exc)), 400

    expires_at = token_payload.get("expire_at") or token_payload.get("expire")
    if not expires_at and token_payload.get("time"):
        expires_at = int(time.time()) + int(token_payload["time"])

    payload = {
        "uid": token_payload.get("uid"),
        "sign": token_payload.get("sign"),
        "time": token_payload.get("time"),
        "app": app,
        "qrImage": encode_qr_image(qr_png),
        "expiresAt": expires_at,
        "raw": token_payload,
    }

    return jsonify({"success": True, "data": payload})


@p115_bp.route("/login/qr/status", methods=["POST"])
@require_auth
def qr_status():
    payload = request.get_json(silent=True) or {}
    token_payload = payload.get("payload") or payload
    if not token_payload.get("uid"):
        return _error("uid is required to poll QR status"), 400
    try:
        status = P115Bridge.qr_status(token_payload)
    except P115BridgeDependencyError as exc:
        return _error(str(exc)), 503
    except P115BridgeError as exc:
        return _error(str(exc)), 400
    return jsonify({"success": True, "data": status})


@p115_bp.route("/login/qr/confirm", methods=["POST"])
@require_auth
def qr_confirm():
    data = request.get_json(silent=True) or {}
    uid = data.get("uid")
    if not uid:
        return _error("uid is required"), 400
    app = data.get("app") or _cloud_config().get("loginApp") or "web"
    user_agent = data.get("userAgent") or _cloud_config().get("userAgent")

    try:
        resp = P115Bridge.complete_qr_login(uid, app=app)
        cookie_payload = resp.get("data") if isinstance(resp.get("data"), dict) else resp
        cookies = cookie_payload.get("cookie")
        if not cookies:
            raise P115BridgeError("QR login response missing cookie data")
        bridge = P115Bridge(cookies=cookies, user_agent=user_agent, app=app)
        profile = bridge.get_user_profile()
        bridge.check_login()
        _persist_cloud115({
            "cookies": cookies,
            "userAgent": user_agent or "",
            "loginApp": app,
            "loginMethod": "qrcode",
        })
    except P115BridgeDependencyError as exc:
        return _error(str(exc)), 503
    except P115BridgeAuthenticationError as exc:
        return _error(str(exc)), 401
    except P115BridgeError as exc:
        return _error(str(exc)), 400

    return jsonify({
        "success": True,
        "data": {
            "profile": profile,
            "loginMethod": "qrcode",
        },
    })


@p115_bp.route("/folders", methods=["GET"])
@require_auth
def list_folders():
    cid = request.args.get("cid", "0")
    try:
        limit = int(request.args.get("limit", 200))
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        return _error("limit and offset must be integers"), 400
    limit = min(max(limit, 1), 1000)
    offset = max(offset, 0)
    try:
        bridge = _get_bridge()
        payload = bridge.list_folders(cid=cid, limit=limit, offset=offset)
    except (ValueError, KeyError) as exc:
        return _error(str(exc)), 400
    except P115BridgeDependencyError as exc:
        return _error(str(exc)), 503
    except P115BridgeAuthenticationError as exc:
        return _error(str(exc)), 401
    except P115BridgeError as exc:
        return _error(str(exc)), 400
    return jsonify({"success": True, "data": payload})


@p115_bp.route("/tasks/offline", methods=["POST"])
@require_auth
def add_offline_task():
    data = request.get_json(silent=True) or {}
    urls = data.get("urls")
    target_cid = data.get("cid") or data.get("wp_path_id") or _cloud_config().get("downloadPath")
    if not urls:
        return _error("urls is required"), 400
    try:
        bridge = _get_bridge()
        resp = bridge.add_offline_tasks(urls, target_cid)
    except (ValueError, KeyError) as exc:
        return _error(str(exc)), 400
    except P115BridgeDependencyError as exc:
        return _error(str(exc)), 503
    except P115BridgeError as exc:
        return _error(str(exc)), 400
    return jsonify({"success": True, "data": resp})


@p115_bp.route("/tasks/offline", methods=["GET"])
@require_auth
def list_offline_tasks():
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        return _error("page must be an integer"), 400
    page = max(page, 1)
    try:
        bridge = _get_bridge()
        resp = bridge.list_offline_tasks(page=page)
    except (ValueError, KeyError) as exc:
        return _error(str(exc)), 400
    except P115BridgeDependencyError as exc:
        return _error(str(exc)), 503
    except P115BridgeError as exc:
        return _error(str(exc)), 400
    return jsonify({"success": True, "data": resp})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_bridge() -> P115Bridge:
    cloud = _cloud_config()
    cookies = cloud.get("cookies")
    if not cookies:
        raise ValueError("115 cookies have not been configured")
    return P115Bridge(cookies=cookies, user_agent=cloud.get("userAgent"), app=cloud.get("loginApp") or "web")


def _cloud_config() -> Dict[str, Any]:
    config = p115_bp.store.get_config()  # type: ignore[attr-defined]
    return config.get("cloud115", {})


def _persist_cloud115(updates: Dict[str, Any]):
    config = p115_bp.store.get_config()  # type: ignore[attr-defined]
    cloud = config.get("cloud115", {})
    cloud.update({k: v for k, v in updates.items() if v is not None})
    config["cloud115"] = cloud
    p115_bp.store.update_config(config)  # type: ignore[attr-defined]


def _error(message: str) -> Dict[str, Any]:
    return {"success": False, "error": message}
