"""Public API of browser_tool.actions.gating: the gate rules for the action tools.

The rules (confirmation.py) say whether a click, dropdown choice or key press is
sensitive and whether it waits for the owner; owner_prompt.py asks or logs.
browser_tool.actions.pointer uses it for every pointer, field and key tool, and
navigation for a back, forward or reload that would resubmit a form.
"""

from browser_tool.actions.gating.confirmation import (
    FocusedTarget,
    click_gate_check,
    focused_target,
    gate_check,
    key_gate_check,
    log_only,
    select_texts,
)
from browser_tool.actions.gating.owner_prompt import (
    GATE_CHANGED,
    GatedAction,
    confirm_or_log,
    ensure_not_stricter,
)

__all__ = [
    "GATE_CHANGED",
    "FocusedTarget",
    "GatedAction",
    "click_gate_check",
    "confirm_or_log",
    "ensure_not_stricter",
    "focused_target",
    "gate_check",
    "key_gate_check",
    "log_only",
    "select_texts",
]
