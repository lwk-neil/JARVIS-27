"""Review or clear Syke's local, argument-free action history."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from core import action_history


def _format_entry(entry: dict[str, Any]) -> str:
    try:
        at = datetime.fromisoformat(str(entry.get("time", "")))
        timestamp = at.astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        timestamp = "unknown time"
    parts = [
        timestamp,
        str(entry.get("tool") or "tool"),
        str(entry.get("action") or "call"),
        str(entry.get("status") or "unknown"),
        f"{int(entry.get('duration_ms') or 0)} ms",
    ]
    hint = action_history.recovery_hint(entry)
    if hint:
        parts.append(hint)
    return " | ".join(parts)


def manage_action_history(parameters: dict, **_context) -> str:
    params = parameters or {}
    action = str(params.get("action", "")).strip().lower()
    if action == "list":
        try:
            entries = action_history.recent(params.get("limit", 20))
        except ValueError as exc:
            return str(exc)
        if not entries:
            return "Action history is empty."
        return "Recent actions (arguments and message contents are not stored):\n" + "\n".join(
            _format_entry(entry) for entry in entries
        )
    if action == "clear":
        removed = action_history.clear()
        return f"Cleared {removed} action history entries."
    return "Specify action: list or clear."


TOOL = {
    "name": "action_history",
    "description": (
        "Show or clear Syke's local action history. It records tool name, "
        "action, outcome category, and duration only; it never stores tool "
        "arguments, page text, or message contents. Use list for recent "
        "activity and clear only when the user asks to erase it."
    ),
    "brief": "Review or clear local action history.",
    "tier": "core",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "list | clear",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Number of recent entries to show, 1-50 (default 20).",
            },
        },
        "required": ["action"],
    },
    "handler": manage_action_history,
}
