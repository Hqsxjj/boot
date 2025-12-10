from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict

from flask import Blueprint, jsonify, request

from middleware.auth import require_auth

webhook_bp = Blueprint("webhook", __name__, url_prefix="/api/webhook")

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_WEBHOOK_LOG = _LOG_DIR / "webhook.log"
_RECENT_EVENTS: Deque[Dict[str, Any]] = deque(maxlen=50)


@webhook_bp.route("/115bot", methods=["POST"])
def ingest_webhook():
    payload = request.get_json(silent=True)
    if payload is None:
        raw = request.data.decode("utf-8", errors="ignore")
        payload = {"raw": raw}
    event = {
        "receivedAt": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
        "headers": dict(request.headers),
    }
    _RECENT_EVENTS.appendleft(event)
    _append_log(event)
    return jsonify({"success": True, "data": {"received": True}})


@webhook_bp.route("/recent", methods=["GET"])
@require_auth
def recent_events():
    return jsonify({"success": True, "data": list(_RECENT_EVENTS)})


def _append_log(event: Dict[str, Any]):
    line = json.dumps(event, ensure_ascii=False)
    with _WEBHOOK_LOG.open("a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")
