import base64
import logging
import os
import threading
import time
from email.utils import formatdate
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote
from xml.sax.saxutils import escape

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
webdav_logger = logging.getLogger("webdav")
if not webdav_logger.handlers:
    handler = logging.FileHandler(LOG_DIR / "webdav.log")
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    webdav_logger.addHandler(handler)
    webdav_logger.setLevel(logging.INFO)


class _WebDavRequestHandler(SimpleHTTPRequestHandler):
    username: Optional[str] = None
    password: Optional[str] = None
    read_only: bool = True
    directory: Optional[str] = None
    server_version = "115BotWebDAV/0.1"

    def _authenticate(self) -> bool:
        if not self.username:
            return True
        header = self.headers.get("Authorization")
        if not header or not header.startswith("Basic "):
            self._send_auth_required()
            return False
        encoded = header.split(" ", 1)[1].strip()
        expected = base64.b64encode(f"{self.username}:{self.password or ''}".encode("utf-8")).decode("utf-8")
        if encoded != expected:
            self._send_auth_required()
            return False
        return True

    def _send_auth_required(self):
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="STRM WebDAV"')
        self.end_headers()

    def do_OPTIONS(self):  # noqa: N802
        if not self._authenticate():
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Allow", "OPTIONS, PROPFIND, GET, HEAD")
        self.send_header("DAV", "1,2")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        if not self._authenticate():
            return
        super().do_GET()

    def do_HEAD(self):  # noqa: N802
        if not self._authenticate():
            return
        super().do_HEAD()

    def do_PUT(self):  # noqa: N802
        if self.read_only:
            self.send_error(HTTPStatus.FORBIDDEN, "Read-only WebDAV server")
            return
        self.send_error(HTTPStatus.NOT_IMPLEMENTED, "PUT not supported in this implementation")

    def do_DELETE(self):  # noqa: N802
        if self.read_only:
            self.send_error(HTTPStatus.FORBIDDEN, "Read-only WebDAV server")
            return
        self.send_error(HTTPStatus.NOT_IMPLEMENTED, "DELETE not supported in this implementation")

    def do_PROPFIND(self):  # noqa: N802
        if not self._authenticate():
            return
        depth = self.headers.get("Depth", "1")
        path = self.translate_path(self.path)
        if not os.path.exists(path):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        entries = self._collect_prop_entries(path, depth)
        body = "<?xml version=\"1.0\" encoding=\"utf-8\"?>" "<D:multistatus xmlns:D=\"DAV:\">" + "".join(entries) + "</D:multistatus>"
        encoded = body.encode("utf-8")
        self.send_response(207)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _collect_prop_entries(self, target_path: str, depth: str) -> list[str]:
        rel = self._rel_href(target_path)
        entries = [self._render_prop(target_path, rel)]
        if depth == "0":
            return entries
        if os.path.isdir(target_path):
            try:
                children = sorted(os.listdir(target_path))
            except OSError:
                children = []
            for name in children:
                child_path = os.path.join(target_path, name)
                entries.append(self._render_prop(child_path, self._rel_href(child_path)))
        return entries

    def _rel_href(self, fs_path: str) -> str:
        directory = Path(self.directory or os.getcwd()).resolve()
        try:
            rel = Path(fs_path).resolve().relative_to(directory)
            href = "/" + rel.as_posix()
        except ValueError:
            href = self.path
        if os.path.isdir(fs_path) and not href.endswith("/"):
            href += "/"
        return href or "/"

    def _render_prop(self, fs_path: str, href: str) -> str:
        name = escape(Path(fs_path).name or "/")
        is_dir = os.path.isdir(fs_path)
        size = os.path.getsize(fs_path) if os.path.isfile(fs_path) else 0
        last_modified = formatdate(os.path.getmtime(fs_path), usegmt=True)
        resource_type = "<D:collection/>" if is_dir else ""
        return (
            "<D:response>"
            f"<D:href>{quote(href)}</D:href>"
            "<D:propstat>"
            "<D:prop>"
            f"<D:displayname>{name}</D:displayname>"
            f"<D:getcontentlength>{size}</D:getcontentlength>"
            f"<D:getlastmodified>{last_modified}</D:getlastmodified>"
            f"<D:resourcetype>{resource_type}</D:resourcetype>"
            "</D:prop>"
            "<D:status>HTTP/1.1 200 OK</D:status>"
            "</D:propstat>"
            "</D:response>"
        )

    def log_message(self, format: str, *args):  # noqa: A003 - matching base signature
        webdav_logger.info("%s - %s", self.address_string(), format % args)


class WebDavServer:
    """Manages the lifecycle of a lightweight WebDAV-like HTTP server."""

    def __init__(self):
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._status: Dict[str, Optional[str | float | bool | int]] = {
            "running": False,
            "port": None,
            "startedAt": None,
            "directory": None,
            "readOnly": True,
            "username": None,
        }

    def start(
        self,
        directory: str,
        *,
        host: str = "0.0.0.0",
        port: int = 8080,
        username: Optional[str] = None,
        password: Optional[str] = None,
        read_only: bool = True,
    ) -> Dict[str, Any]:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        Handler = self._build_handler(path, username, password, read_only)
        with self._lock:
            if self._server:
                return self.status()
            server = ThreadingHTTPServer((host, port), Handler)
            self._server = server
            self._thread = threading.Thread(target=server.serve_forever, daemon=True)
            self._thread.start()
            addr = server.server_address
            self._status.update(
                {
                    "running": True,
                    "port": addr[1],
                    "startedAt": time.time(),
                    "directory": str(path),
                    "readOnly": read_only,
                    "username": username,
                }
            )
            webdav_logger.info("WebDAV server started on %s:%s", addr[0], addr[1])
            return self.status()

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            if not self._server:
                return self.status()
            server = self._server
            thread = self._thread
            server.shutdown()
            server.server_close()
            if thread:
                thread.join(timeout=1)
            self._server = None
            self._thread = None
            self._status.update({"running": False, "port": None, "startedAt": None})
            webdav_logger.info("WebDAV server stopped")
            return self.status()

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._status)

    @staticmethod
    def _build_handler(
        directory: Path,
        username: Optional[str],
        password: Optional[str],
        read_only: bool,
    ) -> type[_WebDavRequestHandler]:
        handler_cls = type(
            "ConfiguredWebDavHandler",
            (_WebDavRequestHandler,),
            {
                "directory": str(directory),
                "username": username,
                "password": password,
                "read_only": read_only,
            },
        )
        return handler_cls


webdav_server = WebDavServer()
