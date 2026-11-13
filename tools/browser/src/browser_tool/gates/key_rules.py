"""Which keys press_key may send freely. Fail-safe: an allowlist, not a denylist.

- Tab, Shift+Tab and Escape only move focus or close things: always free.
- Arrows, Home/End and PageUp/PageDown scroll the page, but change the value of a
  focused control (a <select>, a radio group, a slider): free only when the
  caller has checked that focus is not on a control or widget.
- Paste keys (is_paste_key) are refused outright: they would type the owner's
  real clipboard into the page.
- Every other valid key (Enter, Space, letters, shortcuts) can submit or send,
  so the caller checks it against the [gates] rules (actions/gating).
Control characters ("\\r", "\\n") and unknown key names are rejected, because a raw
"\\r" is an Enter that a name-based check would miss.
"""

KEY_FREE = "free"
KEY_MOVE = "move"
KEY_GATED = "gated"

ALWAYS_FREE_KEYS = frozenset({"tab", "shift+tab", "escape"})
MOVE_KEYS = frozenset(
    {"arrowup", "arrowdown", "arrowleft", "arrowright", "home", "end", "pageup", "pagedown"}
)
MODIFIERS = frozenset({"shift", "control", "alt", "meta", "controlormeta"})
NAMED_KEYS = frozenset(
    ALWAYS_FREE_KEYS
    | MOVE_KEYS
    | {"enter", "numpadenter", "space", "backspace", "delete", "insert"}
    | {f"f{number}" for number in range(1, 13)}
)
# key_name() values the gate rules look at.
ENTER_KEYS = frozenset({"enter", "numpadenter"})
SPACE_KEYS = frozenset({"space", " "})
DELETE_KEY = "delete"
# Enter held with one of these sends in most mail and chat apps, whatever has focus.
SEND_SHORTCUT_MODIFIERS = frozenset({"control", "meta", "controlormeta"})
# Control/Meta+V (these modifiers again) and Shift+Insert paste the clipboard.
PASTE_LETTER = "v"
PASTE_INSERT_KEY = "insert"
PASTE_INSERT_MODIFIER = "shift"


def key_kind(key: str) -> str:
    """Classify `key` as KEY_FREE, KEY_MOVE (free only off controls) or KEY_GATED.

    Args:
        key: A Playwright key: one printable character, or "Mod+...+Name" such as
            "Enter", "Shift+Tab" or "Control+a".

    Raises:
        ValueError: For control characters or an unknown key name.
    """
    if not key or not key.isprintable():
        raise ValueError("control characters are not allowed")
    if len(key) > 1:
        *modifiers, name = key.split("+")
        is_known_name = name.lower() in NAMED_KEYS or (len(name) == 1 and name != " ")
        if not is_known_name or any(part.lower() not in MODIFIERS for part in modifiers):
            raise ValueError(f"unknown key {key!r}")
    if key.lower() in ALWAYS_FREE_KEYS:
        return KEY_FREE
    return KEY_MOVE if key.lower() in MOVE_KEYS else KEY_GATED


def key_name(key: str) -> str:
    """The key without its modifiers, lowercased: "Control+Enter" -> "enter".

    Args:
        key: A key that key_kind accepted.
    """
    return key.lower() if len(key) == 1 else key.split("+")[-1].lower()


def is_send_shortcut(key: str) -> bool:
    """True for Enter held with Control or Meta, e.g. "Control+Enter".

    Args:
        key: A key that key_kind accepted.
    """
    *modifiers, name = key.lower().split("+")
    return name in ENTER_KEYS and not SEND_SHORTCUT_MODIFIERS.isdisjoint(modifiers)


def is_paste_key(key: str) -> bool:
    """True for a key that pastes: Control/Meta+V, also with more modifiers
    (Control+Shift+V pastes plain text), and Shift+Insert.

    Args:
        key: A key that key_kind accepted.
    """
    *modifiers, name = key.lower().split("+")
    if name == PASTE_LETTER:
        return not SEND_SHORTCUT_MODIFIERS.isdisjoint(modifiers)
    return name == PASTE_INSERT_KEY and PASTE_INSERT_MODIFIER in modifiers
