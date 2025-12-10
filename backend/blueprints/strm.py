from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request

from middleware.auth import require_auth
from persistence.store import DataStore
from services.job_runner import job_runner
from services.strm_generator import run_strm_job
from services.webdav import webdav_server

strm_bp = Blueprint("strm", __name__, url_prefix="/api/strm")


def init_strm_blueprint(store: DataStore):
    strm_bp.store = store  # type: ignore[attr-defined]
    return strm_bp


@strm_bp.route("/run", methods=["POST"])
@require_auth
def queue_strm_job():
    data = request.get_json(silent=True) or {}
    module = data.get("module", "115")
    metadata = {
        "module": module,
        "config": strm_bp.store.get_config(),  # type: ignore[attr-defined]
    }
    job_id = job_runner.submit("strm", run_strm_job, metadata=metadata)
    return jsonify({
        "success": True,
        "data": {
            "jobId": job_id,
            "queued": True,
        },
    })


@strm_bp.route("/jobs", methods=["GET"])
@require_auth
def list_jobs():
    return jsonify({"success": True, "data": job_runner.list_jobs()})


@strm_bp.route("/jobs/<job_id>", methods=["GET"])
@require_auth
def get_job(job_id: str):
    job = job_runner.get_job(job_id)
    if not job:
        return _error("Job not found"), 404
    return jsonify({"success": True, "data": job})


@strm_bp.route("/webdav/start", methods=["POST"])
@require_auth
def start_webdav():
    strm_cfg = _strm_config()
    output_dir = strm_cfg.get("outputDir")
    if not output_dir:
        return _error("STRM output directory is not configured"), 400
    dav_cfg = strm_cfg.get("webdav", {})
    try:
        port = int(dav_cfg.get("port", 8080))
    except (TypeError, ValueError):
        return _error("WebDAV port must be an integer"), 400
    username = dav_cfg.get("username") or None
    password = dav_cfg.get("password") or None
    read_only = bool(dav_cfg.get("readOnly", True))
    try:
        status = webdav_server.start(
            output_dir,
            port=port,
            username=username,
            password=password,
            read_only=read_only,
        )
    except OSError as exc:
        return _error(f"Failed to start WebDAV server: {exc}"), 500
    return jsonify({"success": True, "data": status})


@strm_bp.route("/webdav/stop", methods=["POST"])
@require_auth
def stop_webdav():
    status = webdav_server.stop()
    return jsonify({"success": True, "data": status})


@strm_bp.route("/webdav/status", methods=["GET"])
@require_auth
def webdav_status():
    return jsonify({"success": True, "data": webdav_server.status()})


def _strm_config() -> Dict[str, Any]:
    config = strm_bp.store.get_config()  # type: ignore[attr-defined]
    return config.get("strm", {})


def _error(message: str):
    return {"success": False, "error": message}
