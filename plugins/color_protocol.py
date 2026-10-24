"""Voice-controlled HUD color protocols."""

PLUGIN = {
    "name": "color_protocol",
    "description": (
        "Change the assistant HUD and holographic avatar accent color when the "
        "user says a color followed by 'protocol', for example 'red protocol' "
        "or 'blue protocol'. Also handle 'black and white protocol', "
        "'monochrome protocol', and requests to switch the HUD color. Do not "
        "use this for controlling physical smart-home lights. Apply the color "
        "live through this tool only. Never restart, relaunch, or shut down "
        "the assistant or computer for a color change."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "color": {
                "type": "STRING",
                "description": (
                    "The requested color name, such as red, orange, yellow, "
                    "green, cyan, blue, purple, pink, white, or black and white."
                ),
            },
        },
        "required": ["color"],
    },
}

_COLORS = {
    "red": ("#ff3333", "red"),
    "orange": ("#ff8c24", "orange"),
    "yellow": ("#f5d742", "yellow"),
    "green": ("#34d17b", "green"),
    "cyan": ("#25d9e8", "cyan"),
    "blue": ("#4287ff", "blue"),
    "purple": ("#a855f7", "purple"),
    "pink": ("#ff5caa", "pink"),
    "white": ("#f5f5f5", "white"),
    "black": ("#f5f5f5", "black and white"),
    "black and white": ("#f5f5f5", "black and white"),
    "white and black": ("#f5f5f5", "black and white"),
    "monochrome": ("#f5f5f5", "black and white"),
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    color = " ".join(str(parameters.get("color", "")).strip().lower().split())
    selected = _COLORS.get(color)
    if selected is None:
        choices = ", ".join(_COLORS)
        return f"That color protocol is not available. Choose from: {choices}."

    if player is None or not callable(getattr(player, "set_ui_color", None)):
        return "I could not change the HUD color because the display is unavailable."

    hex_color, label = selected
    player.set_ui_color(hex_color)
    return (
        f"{label.title()} protocol activated. The HUD color changed live; "
        "no restart was needed."
    )
