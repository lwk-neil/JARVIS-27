from __future__ import annotations

from dataclasses import dataclass

from core.browser_bridge import browser_bridge
from memory.config_manager import get_permission_mode


@dataclass(frozen=True)
class PermissionDecision:
    kind: str
    reason: str = ""
    title: str = ""
    detail: str = ""


_READ_ONLY_TOOLS = {
    "close_camera",
    "flight_finder",
    "recall_memory",
    "system_status",
    "weather_report",
    "web_search",
}

_READ_ONLY_ACTIONS = {
    "action_history": {"list"},
    "browser_control": {"cancel", "get_text", "get_url", "list_browsers", "status"},
    "manage_preferences": {"get", "list"},
    "desktop_control": {"current_wallpaper", "list", "stats"},
    "file_controller": {"disk_usage", "find", "info", "largest", "list", "read"},
    "file_processor": {
        "analyze", "describe", "extract_text", "explain", "info", "list",
        "ocr", "read", "review", "stats", "summarize", "validate", "word_count",
    },
    "manage_monitor": {"list"},
    "undo": {"list"},
    "youtube_video": {"get_info", "summarize", "trending"},
}

_BROWSER_INTERACTIONS = {
    "back", "click", "close", "close_all", "close_tab", "fill_form",
    "forward", "go_to", "new_tab", "press", "reload", "scroll", "search",
    "smart_click", "smart_type", "switch", "type",
}


def _action(parameters: dict) -> str:
    value = parameters.get("action", "")
    return value.strip().lower() if isinstance(value, str) else ""


def evaluate_tool(
    name: str,
    parameters: dict,
    mode: str | None = None,
) -> PermissionDecision:
    """Apply the selected permission profile before dispatching a tool."""
    active_mode = (
        mode if mode in {"normal", "trusted", "unlimited", "restricted"}
        else get_permission_mode()
    )
    action = _action(parameters)

    if active_mode == "restricted":
        if name in _READ_ONLY_TOOLS:
            return PermissionDecision("allow")
        if action in _READ_ONLY_ACTIONS.get(name, set()):
            return PermissionDecision("allow")
        return PermissionDecision(
            "deny",
            reason=(
                f"{name} {action or 'operation'} is disabled in Restricted mode. "
                "Switch to Normal or Trusted Automation to allow changes."
            ),
        )

    if (name == "browser_control" and parameters.get("browser") == "current"
            and action in _BROWSER_INTERACTIONS and not browser_bridge.connected()):
        return PermissionDecision(
            "deny",
            reason=(
                "No current browser tab is paired. Click the Syke Current Tab "
                "extension on the website, then retry."
            ),
        )

    return PermissionDecision("allow")
