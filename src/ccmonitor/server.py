from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .collector import UsageCollector


def serve(
    collector: UsageCollector,
    static_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    static_root = static_dir.resolve()

    class MonitorHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/data":
                self._serve_json()
                return

            self._serve_static(parsed.path)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _serve_json(self) -> None:
            payload = collector.collect()
            body = json.dumps(payload).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _serve_static(self, request_path: str) -> None:
            relative = request_path.lstrip("/") or "index.html"
            candidate = (static_root / relative).resolve()

            if static_root not in candidate.parents and candidate != static_root:
                self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
                return

            if candidate.is_dir():
                candidate = candidate / "index.html"

            if not candidate.exists() or not candidate.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
                return

            content_type, _ = mimetypes.guess_type(candidate.name)
            try:
                body = candidate.read_bytes()
            except OSError:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Read failed")
                return

            self.send_response(HTTPStatus.OK)
            self.send_header(
                "Content-Type",
                f"{content_type or 'application/octet-stream'}; charset=utf-8",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), MonitorHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
