from __future__ import annotations

from typing import Any, Dict

import requests
from flask import Blueprint, jsonify, request

from middleware.auth import require_auth
from persistence.store import DataStore
from services import emby as emby_service

emby_bp = Blueprint("emby", __name__, url_prefix="/api/emby")


def init_emby_blueprint(store: DataStore):
    emby_bp.store = store  # type: ignore[attr-defined]
    return emby_bp


@emby_bp.route("/test", methods=["POST"])
@require_auth
def test_connection():
    data = request.get_json(silent=True) or {}
    config = _config()
    server_url = data.get("serverUrl") or config.get("serverUrl")
    api_key = data.get("apiKey") or config.get("apiKey")
    if not server_url:
        return _error("serverUrl is required"), 400
    try:
        info = emby_service.test_connection(server_url, api_key)
        if data.get("persist"):
            _persist_emby({"serverUrl": server_url, "apiKey": api_key})
    except ValueError as exc:
        return _error(str(exc)), 400
    except requests.RequestException as exc:  # pragma: no cover - network errors
        return _error(f"Failed to reach Emby server: {exc}"), 502
    return jsonify({"success": True, "data": info})


@emby_bp.route("/missing", methods=["GET"])
@require_auth
def missing_episodes():
    config = _config()
    server_url = config.get("serverUrl")
    api_key = config.get("apiKey")
    if not server_url:
        return _error("Emby server URL is not configured"), 400
    try:
        limit = int(request.args.get("limit", 25))
    except (TypeError, ValueError):
        return _error("limit must be an integer"), 400
    limit = min(max(limit, 1), 200)
    try:
        items = emby_service.fetch_missing_episodes(server_url, api_key, limit=limit)
    except ValueError as exc:
        return _error(str(exc)), 400
    except requests.RequestException as exc:  # pragma: no cover - network errors
        return _error(f"Failed to query Emby server: {exc}"), 502
    return jsonify({
        "success": True,
        "data": {
            "items": items,
            "count": len(items),
        },
    })


def _config() -> Dict[str, Any]:
    config = emby_bp.store.get_config()  # type: ignore[attr-defined]
    return config.get("emby", {})


def _persist_emby(updates: Dict[str, Any]):
    config = emby_bp.store.get_config()  # type: ignore[attr-defined]
    emby_cfg = config.get("emby", {})
    emby_cfg.update({k: v for k, v in updates.items() if v is not None})
    config["emby"] = emby_cfg
    emby_bp.store.update_config(config)  # type: ignore[attr-defined]


def _error(message: str) -> Dict[str, Any]:
    return {"success": False, "error": message}
