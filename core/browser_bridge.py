"""Loopback bridge between Syke and the explicitly paired browser tab."""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


_PORT = 18765
_MAX_BODY = 1_000_000
_TAB_TIMEOUT = 45.0
_COMMAND_TIMEOUT = 45.0


class BrowserBridge:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._token = ""
        self._jobs: dict[str, dict[str, Any]] = {}
        self._queue: deque[str] = deque()
        self._active_tab: dict[str, Any] | None = None

    @staticmethod
    def token_path() -> Path:
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / ".local" / "share"
        return root / "Syke" / "browser_bridge.token"

    def start(self) -> None:
        if self._server is not None:
            return

        token_path = self.token_path()
        token_path.parent.mkdir(parents=True, exist_ok=True)
        if token_path.exists():
            token = token_path.read_text(encoding="utf-8").strip()
            if len(token) < 32:
                raise RuntimeError(f"Invalid browser bridge token file: {token_path}")
        else:
            token = secrets.token_urlsafe(32)
            token_path.write_text(token, encoding="utf-8")
            try:
                token_path.chmod(0o600)
            except OSError:
                pass

        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *args: Any) -> None:
                return

            def _origin_allowed(self) -> bool:
                origin = self.headers.get("Origin", "")
                return origin.startswith((
                    "chrome-extension://",
                    "edge-extension://",
                ))

            def _authorize(self) -> bool:
                auth = self.headers.get("Authorization", "")
                supplied = auth.removeprefix("Bearer ").strip()
                return (
                    self._origin_allowed()
                    and secrets.compare_digest(supplied, bridge._token)
                )

            def _send_json(self, status: int, data: dict[str, Any]) -> None:
                payload = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                origin = self.headers.get("Origin", "")
                if self._origin_allowed():
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                self.end_headers()
                self.wfile.write(payload)

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > _MAX_BODY:
                    raise ValueError("Invalid request size.")
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise ValueError("Expected a JSON object.")
                return value

            def do_OPTIONS(self) -> None:
                if not self._origin_allowed():
                    self.send_error(403)
                    return
                self.send_response(204)
                self.send_header(
                    "Access-Control-Allow-Origin", self.headers["Origin"])
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Authorization, Content-Type, X-Syke-Tab-Id",
                )
                self.send_header("Access-Control-Max-Age", "600")
                self.end_headers()

            def do_GET(self) -> None:
                if not self._authorize():
                    self._send_json(403, {"error": "Not authorized."})
                    return
                if self.path != "/next":
                    if self.path == "/status":
                        self._send_json(200, bridge.status())
                        return
                    self._send_json(404, {"error": "Unknown endpoint."})
                    return
                try:
                    tab_id = int(self.headers.get("X-Syke-Tab-Id", ""))
                except ValueError:
                    self._send_json(400, {"error": "Invalid tab id."})
                    return

                with bridge._condition:
                    current = bridge._active_tab or {}
                    bridge._active_tab = {
                        **(current if current.get("tab_id") == tab_id else {}),
                        "tab_id": tab_id,
                        "last_seen": time.monotonic(),
                    }
                    job = bridge._take_job(tab_id)
                    if job is None:
                        bridge._condition.wait(timeout=20)
                        job = bridge._take_job(tab_id)
                self._send_json(200, job or {})

            def do_POST(self) -> None:
                if not self._authorize():
                    self._send_json(403, {"error": "Not authorized."})
                    return
                try:
                    data = self._read_json()
                except (ValueError, json.JSONDecodeError) as exc:
                    self._send_json(400, {"error": str(exc)})
                    return

                if self.path == "/register":
                    try:
                        tab_id = int(data["tab_id"])
                    except (KeyError, TypeError, ValueError):
                        self._send_json(400, {"error": "Invalid tab id."})
                        return
                    with bridge._condition:
                        bridge._active_tab = {
                            "tab_id": tab_id,
                            "last_seen": time.monotonic(),
                            "url": str(data.get("url", ""))[:2_000],
                            "title": str(data.get("title", ""))[:500],
                        }
                        bridge._condition.notify_all()
                    self._send_json(200, {"connected": True})
                    return

                if self.path == "/disconnect":
                    try:
                        tab_id = int(data["tab_id"])
                    except (KeyError, TypeError, ValueError):
                        self._send_json(400, {"error": "Invalid tab id."})
                        return
                    with bridge._condition:
                        if (bridge._active_tab
                                and bridge._active_tab.get("tab_id") == tab_id):
                            bridge._active_tab = None
                        for job in bridge._jobs.values():
                            if job["tab_id"] == tab_id and job["result"] is None:
                                job["result"] = (
                                    "The paired browser tab disconnected before "
                                    "the command completed."
                                )
                        bridge._condition.notify_all()
                    self._send_json(200, {"connected": False})
                    return

                if self.path == "/result":
                    job_id = str(data.get("job_id", ""))
                    with bridge._condition:
                        job = bridge._jobs.get(job_id)
                        if job is None:
                            self._send_json(404, {"error": "Command expired."})
                            return
                        job["result"] = data.get("result")
                        bridge._condition.notify_all()
                    self._send_json(200, {"received": True})
                    return

                self._send_json(404, {"error": "Unknown endpoint."})

        self._token = token
        self._server = ThreadingHTTPServer(("127.0.0.1", _PORT), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="SykeBrowserBridge",
        )
        self._thread.start()

    def _take_job(self, tab_id: int) -> dict[str, Any] | None:
        for _ in range(len(self._queue)):
            job_id = self._queue.popleft()
            job = self._jobs.get(job_id)
            if job is None or job["result"] is not None:
                continue
            if job["tab_id"] == tab_id:
                job["dispatched"] = True
                return {
                    "job_id": job_id,
                    "action": job["action"],
                    "parameters": job["parameters"],
                }
            self._queue.append(job_id)
        return None

    def status(self) -> dict[str, Any]:
        with self._condition:
            tab = self._active_tab
            connected = bool(
                tab and time.monotonic() - tab["last_seen"] < _TAB_TIMEOUT
            )
            queued = sum(
                1 for job in self._jobs.values()
                if job["result"] is None and not job.get("dispatched")
            )
            running = sum(
                1 for job in self._jobs.values()
                if job["result"] is None and job.get("dispatched")
            )
            return {
                "connected": connected,
                "title": str(tab.get("title", ""))[:200] if connected else "",
                "url": str(tab.get("url", ""))[:500] if connected else "",
                "queued": queued,
                "running": running,
            }

    def cancel_queued(self) -> int:
        """Cancel commands not yet handed to the extension; running page code is atomic."""
        with self._condition:
            cancelled = 0
            for job in self._jobs.values():
                if job["result"] is None and not job.get("dispatched"):
                    job["result"] = (
                        "Cancelled before the browser extension started the action."
                    )
                    cancelled += 1
            self._condition.notify_all()
            return cancelled

    def connected(self) -> bool:
        with self._condition:
            return bool(
                self._active_tab
                and time.monotonic() - self._active_tab["last_seen"] < _TAB_TIMEOUT
            )

    def page_label(self) -> str:
        with self._condition:
            tab = self._active_tab
            if not tab or time.monotonic() - tab["last_seen"] >= _TAB_TIMEOUT:
                return "paired current tab"
            title = str(tab.get("title", "")).strip()
            host = urlparse(str(tab.get("url", ""))).hostname or ""
            parts = [part for part in (title, host) if part]
            return " — ".join(parts) or "paired current tab"

    def submit(self, action: str, parameters: dict[str, Any]) -> str | None:
        with self._condition:
            if not self._active_tab or (
                time.monotonic() - self._active_tab["last_seen"] >= _TAB_TIMEOUT
            ):
                return None
            job_id = uuid.uuid4().hex
            job = {
                "tab_id": self._active_tab["tab_id"],
                "action": action,
                "parameters": parameters,
                "result": None,
            }
            self._jobs[job_id] = job
            self._queue.append(job_id)
            self._condition.notify_all()

            deadline = time.monotonic() + _COMMAND_TIMEOUT
            while job["result"] is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._jobs.pop(job_id, None)
                    return "The paired browser did not respond before the command timed out."
                self._condition.wait(timeout=remaining)

            result = job["result"]
            self._jobs.pop(job_id, None)

        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)


browser_bridge = BrowserBridge()
