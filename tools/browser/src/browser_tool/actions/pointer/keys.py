"""The keyboard tool: press_key on the focused element.

It first refuses a tab showing a Duo prompt (owner-only) and checks the page
origin, and checks both again right before the key is pressed, since an owner
dialog can wait up to minutes (guards.ensure_ready_to_act, through
after_action.act_and_report). press_key is an
allowlist: Tab/Shift+Tab/Escape pass; arrows, Home/End and PageUp/PageDown pass
only when focus is not on a control or widget; every other key goes through the
gate rules and is refused outright in a password/OTP field. Paste keys are
refused, since they would type the owner's clipboard. A key that lands on a
login page gets the signed-out note (after_action.act_and_report).
"""

from playwright.async_api import Page

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.gating import (
    FocusedTarget,
    GatedAction,
    confirm_or_log,
    focused_target,
    key_gate_check,
)
from browser_tool.actions.navigation import KEY_START_GRACE_S
from browser_tool.actions.pointer.after_action import act_and_report
from browser_tool.actions.pointer.target import prepare_page
from browser_tool.gates import KEY_FREE, KEY_GATED, is_paste_key, key_kind
from browser_tool.redaction import is_focus_on_sensitive_field

PASTE_REFUSAL = "refused: paste keys would type the owner's clipboard; use type_text instead"


async def press_key(ctx: ActionContext, key: str) -> str:
    """Press a key (e.g. "Enter", "Tab", "Control+A") on the focused element."""
    try:
        kind = key_kind(key)
    except ValueError as error:
        raise ActionError(f"bad key: {error}; use a name such as Enter, Tab or Control+A") from None
    if is_paste_key(key):
        raise ActionError(PASTE_REFUSAL)
    page = await prepare_page(ctx)
    approved_origin = None
    trigger = [key]
    if kind != KEY_FREE:
        focus = await focused_target(page)
        trigger += focus.texts
        # Move keys change the value of a focused control or widget: gate them there.
        if kind == KEY_GATED or focus.is_control:
            approved_origin = await _gate_key(ctx, page, key, focus)
    # Unlike a click, a key press returns before a navigation it set off starts.
    start_grace_s = 0.0 if kind == KEY_FREE else KEY_START_GRACE_S
    # act_and_report checks again right before the press: a gated key waits for
    # the owner, and the tab may have gone to Duo (e.g. after
    # fill_login(submit=True)), where Enter would answer it, or to another site
    # the owner never approved the key for.
    return await act_and_report(
        ctx,
        page,
        approved_origin,
        lambda: page.keyboard.press(key),
        f"pressed {key}",
        start_grace_s=start_grace_s,
        trigger=trigger,
    )


async def _gate_key(ctx: ActionContext, page: Page, key: str, focus: FocusedTarget) -> str | None:
    """Refuse the key in a secret field; otherwise ask the owner or log it.

    Returns:
        The origin the owner approved, or None when the key needed no approval.
    """
    if await is_focus_on_sensitive_field(page):
        raise ActionError(ctx.password_field_refusal)
    # A single character is typed text, so the log names only named keys and shortcuts.
    shown_key = key if len(key) > 1 else "a character key"
    action = GatedAction(
        f"press {key} on the focused element", f"press_key {shown_key}", focus.frame_origin
    )
    return await confirm_or_log(ctx, page, action, key_gate_check(ctx, page, key, focus))
