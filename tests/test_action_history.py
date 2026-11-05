import json
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest import mock
from collections import deque

from actions.action_history import manage_action_history
from core import action_history
from core.browser_bridge import BrowserBridge
from core.permission_modes import evaluate_tool


class ActionHistoryTests(unittest.TestCase):
    def test_history_keeps_only_bounded_action_metadata(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            action_history, "HISTORY_PATH", Path(directory) / "history.json"
        ):
            action_history.record(
                "send_message", "send", "unverified", 42
            )
            stored = json.loads(action_history.HISTORY_PATH.read_text("utf-8"))
            rendered = manage_action_history({"action": "list"})

        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["tool"], "send_message")
        self.assertEqual(stored[0]["status"], "unverified")
        self.assertNotIn("message_text", stored[0])
        self.assertIn("avoid duplicate messages", rendered)
        self.assertNotIn("message_text", rendered)

    def test_history_clear_runs_without_confirmation_but_not_in_restricted_mode(self):
        normal = evaluate_tool(
            "action_history", {"action": "clear"}, mode="normal"
        )
        restricted = evaluate_tool(
            "action_history", {"action": "clear"}, mode="restricted"
        )

        self.assertEqual(normal.kind, "allow")
        self.assertEqual(restricted.kind, "deny")
        self.assertEqual(
            evaluate_tool(
                "action_history", {"action": "list"}, mode="restricted"
            ).kind,
            "allow",
        )

    def test_invalid_history_limit_returns_a_clear_error(self):
        result = manage_action_history({"action": "list", "limit": "many"})

        self.assertEqual(result, "History limit must be a whole number.")


class BrowserTaskControlTests(unittest.TestCase):
    def test_browser_status_and_cancel_are_safe_in_restricted_mode(self):
        for action in ("status", "cancel"):
            with self.subTest(action=action):
                decision = evaluate_tool(
                    "browser_control", {"action": action}, mode="restricted"
                )
                self.assertEqual(decision.kind, "allow")

    def test_cancel_only_stops_browser_commands_not_yet_dispatched(self):
        bridge = BrowserBridge()
        bridge._active_tab = {"tab_id": 7, "last_seen": time.monotonic()}
        bridge._jobs = {
            "queued": {
                "tab_id": 7, "result": None, "dispatched": False,
                "action": "click", "parameters": {},
            },
            "running": {
                "tab_id": 7, "result": None, "dispatched": True,
                "action": "type", "parameters": {},
            },
        }
        bridge._queue = deque(["queued"])

        self.assertEqual(bridge.cancel_queued(), 1)
        self.assertIn("Cancelled before", bridge._jobs["queued"]["result"])
        self.assertIsNone(bridge._jobs["running"]["result"])
        self.assertEqual(bridge.status()["queued"], 0)
        self.assertEqual(bridge.status()["running"], 1)

    def test_browser_status_expires_a_stale_pairing(self):
        bridge = BrowserBridge()
        bridge._active_tab = {
            "tab_id": 7,
            "last_seen": time.monotonic() - 60,
            "title": "Old page",
            "url": "https://example.test/",
        }

        self.assertFalse(bridge.status()["connected"])

    def test_status_endpoint_requires_extension_origin_and_pairing_token(self):
        bridge = BrowserBridge()
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(
                    bridge, "token_path",
                    return_value=Path(directory) / "bridge.token",
                ), mock.patch(
                    "core.browser_bridge._PORT", 0
                ):
            bridge.start()
            bridge._active_tab = {
                "tab_id": 11,
                "last_seen": time.monotonic(),
                "title": "Example",
                "url": "https://example.test/",
            }
            port = bridge._server.server_address[1]
            try:
                request = Request(
                    f"http://127.0.0.1:{port}/status",
                    headers={
                        "Origin": "chrome-extension://test-extension",
                        "Authorization": f"Bearer {bridge._token}",
                    },
                )
                with urlopen(request, timeout=3) as response:
                    status = json.loads(response.read())
                self.assertTrue(status["connected"])
                self.assertEqual(status["title"], "Example")

                unauthorized = Request(
                    f"http://127.0.0.1:{port}/status",
                    headers={
                        "Origin": "https://example.test",
                        "Authorization": f"Bearer {bridge._token}",
                    },
                )
                with self.assertRaises(HTTPError) as error:
                    urlopen(unauthorized, timeout=3)
                self.assertEqual(error.exception.code, 403)
            finally:
                bridge._server.shutdown()
                bridge._server.server_close()
                bridge._thread.join(timeout=3)
