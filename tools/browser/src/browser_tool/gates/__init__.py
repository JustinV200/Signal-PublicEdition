"""Public API of browser_tool.gates: owner confirmation for sensitive actions."""

from browser_tool.gates.action_rules import ActionRules
from browser_tool.gates.confirm_rules import ConfirmRules, GateCheck, strictest
from browser_tool.gates.confirmer import ConfirmationRequest, Confirmer
from browser_tool.gates.dialog_confirmer import DialogConfirmer, build_dialog_text
from browser_tool.gates.key_rules import (
    DELETE_KEY,
    ENTER_KEYS,
    KEY_FREE,
    KEY_GATED,
    KEY_MOVE,
    SPACE_KEYS,
    is_paste_key,
    is_send_shortcut,
    key_kind,
    key_name,
)

__all__ = [
    "DELETE_KEY",
    "ENTER_KEYS",
    "KEY_FREE",
    "KEY_GATED",
    "KEY_MOVE",
    "SPACE_KEYS",
    "ActionRules",
    "ConfirmRules",
    "ConfirmationRequest",
    "Confirmer",
    "DialogConfirmer",
    "GateCheck",
    "build_dialog_text",
    "is_paste_key",
    "is_send_shortcut",
    "key_kind",
    "key_name",
    "strictest",
]
