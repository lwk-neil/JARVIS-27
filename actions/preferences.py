"""Review and manage the user's saved preferences."""
from __future__ import annotations

from memory import memory_manager


def manage_preferences(parameters: dict, **_context) -> str:
    params = parameters or {}
    action = str(params.get("action", "")).strip().lower()

    if action == "list":
        entries = [
            item for item in memory_manager.all_entries_for_ui()
            if item.get("category") == "preferences"
        ]
        if not entries:
            return "No saved preferences."
        return "Saved preferences:\n" + "\n".join(
            f"- {item['key']}: {item['value']}" for item in entries
        )

    key = str(params.get("key", "")).strip()
    if not key:
        return "Specify the preference key."

    if action == "get":
        preferences = memory_manager.load_memory().get("preferences", {})
        entry = preferences.get(key) if isinstance(preferences, dict) else None
        value = memory_manager._entry_value(entry)
        return f"{key}: {value}" if value else f"No saved preference named '{key}'."

    if action == "set":
        value = str(params.get("value", "")).strip()
        if not value:
            return "Specify a non-empty preference value."
        memory_manager.update_memory(
            {"preferences": {key: {"value": value}}}
        )
        return f"Saved preference: {key}."

    if action == "remove":
        return memory_manager.forget(key, "preferences")

    return "Specify action: list, get, set, or remove."


TOOL = {
    "name": "manage_preferences",
    "description": (
        "Review, save, look up, or remove the user's long-term preferences. "
        "Use this for preferences only, not one-time instructions or tasks. "
        "Ask no extra questions when the preference is clear. "
        "Actions: list, get, set, remove."
    ),
    "brief": "Review, save, look up, or remove saved user preferences.",
    "tier": "core",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "list | get | set | remove",
            },
            "key": {
                "type": "STRING",
                "description": "Preference name, such as response_style or browser.",
            },
            "value": {
                "type": "STRING",
                "description": "Preference value, required for set.",
            },
        },
        "required": ["action"],
    },
    "handler": manage_preferences,
}
