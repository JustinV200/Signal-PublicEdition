"""Public API of browser_tool.actions.pointer: the tools that act on the page.

click, click_at and drag go through the click rules (clicks.py, click_at.py,
drag.py); hover and scroll only log (passive.py); type_text and select_option
fill fields (fields.py); press_key acts on the focused element (keys.py).
target.py holds their shared prelude, after_action.py their last-moment check
and result; both are exported for the other acting tools (answer_dialog,
upload_file).
"""

from browser_tool.actions.pointer.after_action import act_and_report
from browser_tool.actions.pointer.click_at import click_at
from browser_tool.actions.pointer.clicks import click
from browser_tool.actions.pointer.drag import drag
from browser_tool.actions.pointer.fields import select_option, type_text
from browser_tool.actions.pointer.keys import press_key
from browser_tool.actions.pointer.passive import hover, scroll
from browser_tool.actions.pointer.target import RefTarget, log_target, prepare_ref

__all__ = [
    "RefTarget",
    "act_and_report",
    "click",
    "click_at",
    "drag",
    "hover",
    "log_target",
    "prepare_ref",
    "press_key",
    "scroll",
    "select_option",
    "type_text",
]
