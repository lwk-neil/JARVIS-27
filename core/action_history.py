"""Small, local-only audit trail of Syke tool calls without argument contents."""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory.memory_manager import BASE_DIR


MAX_ENTRIES = 200
_lock = threading.RLock()


HISTORY_PATH = BASE_DIR / "memory" / "action_history.json"


def _read() -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    try:
        payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read action history: {exc}") from exc
    if not isinstance(payload, list):
        raise RuntimeError("Action history file has an invalid format.")
    return [entry for entry in payload if isinstance(entry, dict)]


def record(
    tool: str,
    action: str,
    status: str,
    duration_ms: int = 0,
) -> None:
    """Append metadata only; never persist tool arguments, page text, or messages."""
    event = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": re.sub(r"[^a-zA-Z0-9_-]", "", str(tool))[:64],
        "action": re.sub(r"[^a-zA-Z0-9_-]", "", str(action))[:48],
        "status": re.sub(r"[^a-zA-Z0-9_-]", "", str(status))[:32],
        "duration_ms": max(0, min(int(duration_ms), 86_400_000)),
    }
    with _lock:
        entries = _read()
        entries.append(event)
        entries = entries[-MAX_ENTRIES:]
        temporary = HISTORY_PATH.with_name(HISTORY_PATH.name + ".tmp")
        try:
            HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(entries, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
            temporary.replace(HISTORY_PATH)
        except OSError as exc:
            raise RuntimeError(f"Could not save action history: {exc}") from exc


def recent(limit: int = 20) -> list[dict[str, Any]]:
    try:
        limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("History limit must be a whole number.") from exc
    limit = max(1, min(limit, 50))
    with _lock:
        return list(reversed(_read()[-limit:]))


def clear() -> int:
    with _lock:
        entries = _read()
        try:
            HISTORY_PATH.unlink(missing_ok=True)
        except OSError as exc:
            raise RuntimeError(f"Could not clear action history: {exc}") from exc
        return len(entries)


def recovery_hint(entry: dict[str, Any]) -> str:
    if entry.get("status") not in {"failed", "unverified"}:
        return ""
    tool = entry.get("tool")
    if tool == "send_message":
        return "Check the conversation before retrying to avoid duplicate messages."
    if tool == "browser_control":
        return "Check the paired tab and its connection before retrying."
    if tool in {"file_controller", "file_processor"}:
        return "Check the target file or folder before retrying."
    return "Check the affected app or device before retrying."
