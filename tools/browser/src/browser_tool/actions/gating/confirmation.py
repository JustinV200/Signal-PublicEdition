"""Decide whether an action is sensitive, and whether it waits for the owner.

Every rule returns a GateCheck (browser_tool.gates); [gates] always_confirm
decides which categories ask, and owner_prompt.confirm_or_log asks or logs.
Rules by category:
- purchase / send / delete: the target's text matches the category's patterns;
- send: a submit control in a form that isn't a search form, an explicit GET
  form or a sign-in form (one with a password field), unless it is a
  save-draft button; Enter in a non-search form's only
  text input when it has no submit button (implicit submission); Enter with
  Control or Meta anywhere but a search box; Enter in a message box (textarea
  or contenteditable), except on [gates] no_confirm_origins;
- delete: the Delete key;
- log only: a target in a frame with an unverified origin, a click that would
  land in an <iframe>, any other non-navigation key press, and whatever hover
  and scroll touch (log_only).
Signing in doesn't ask: the owner wants approval only for purchases, sends and
deletes, and the vault asks for every fill_login anyway. A submit skips the send
rule only when its own form is a sign-in form (page_scripts.isSignInForm) and
its label is sign-in wording (config.SIGN_IN_WORDING_RE).
For clicks, the text and form rules run on the element actually hit at the
click point and on every ancestor of it and of the target, across shadow hosts,
plus a clicked <label>'s control (clicks bubble, and label clicks act on the
control). For keys they run on the focused element and its form's submit
controls. Move keys (arrows, Home, End, PageUp/Down) only reach these rules when
focus is on a control. Text is read live from the page (main world) and
combined with the snapshot label. Only button-like values and <option> labels
are read, never field values.
"""

import logging
import re
from dataclasses import replace
from typing import NamedTuple

from playwright.async_api import ElementHandle, Locator, Page
from playwright.async_api import Error as PlaywrightError

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.gating.page_scripts import (
    ELEMENT_INFO_JS,
    FOCUSED_TEXTS_JS,
    OPTION_TEXTS_JS,
)
from browser_tool.config import (
    CATEGORY_DELETE,
    CATEGORY_SEND,
    SIGN_IN_WORDING_RE,
)
from browser_tool.gates import (
    DELETE_KEY,
    ENTER_KEYS,
    SPACE_KEYS,
    GateCheck,
    is_send_shortcut,
    key_name,
    strictest,
)
from browser_tool.policy import origin_of

logger = logging.getLogger(__name__)

UNVERIFIED_FRAME_REASON = "the element is in a frame with an unverified origin"
FORM_SUBMIT_REASON = "it submits a form"
MESSAGE_BOX_REASON = "Enter in a message box can send it"
SEND_SHORTCUT_REASON = "Control+Enter sends in most mail and chat apps"
DELETE_KEY_REASON = "the Delete key can delete the selected item"
KEY_PRESS_REASON = "key presses can submit forms or send messages"
NOT_A_DROPDOWN = (
    "refused: that ref is not a dropdown (<select>); "
    "for a custom dropdown, click it, then click the option"
)
NO_SUCH_OPTION = "refused: no option with that value or label; take a new snapshot"
# Only "Save draft" / "Save as draft" keeps work local for sure: in Moodle with
# drafts off, "Save changes" hands the assignment in.
SAVE_DRAFT_RE = re.compile(r"\s*save\s+(as\s+)?draft\b", re.IGNORECASE)


class FocusedTarget(NamedTuple):
    """What a key press would act on.

    Attributes:
        texts: The focused element's text and its form's submit controls' texts.
        frame_origin: Its frame's origin when that frame is a child frame, else None.
        is_control: Focus is on a form control or widget (move keys change it).
        is_submit: The focused element is a submit control.
        submit_text: The text of the submit control Enter would press in a form
            that isn't a search form ("" for an implicit submission), else None.
        in_sign_in_form: That form is a sign-in form.
        is_search: Focus is in a search box or a search form.
        is_message_box: Focus is in a textarea or contenteditable that isn't a
            search box.
    """

    texts: list[str]
    frame_origin: str | None
    is_control: bool = False
    is_submit: bool = False
    submit_text: str | None = None
    in_sign_in_form: bool = False
    is_search: bool = False
    is_message_box: bool = False


def gate_check(ctx: ActionContext, texts: list[str], frame_origin: str | None) -> GateCheck | None:
    """The text rules plus the unverified-frame rule, or None if neither applies.

    Args:
        ctx: The action context.
        texts: The target's texts.
        frame_origin: The target frame's origin when it is unverified, else None.
    """
    frame = ctx.rules.check(None, UNVERIFIED_FRAME_REASON) if frame_origin else None
    return strictest(ctx.rules.check_texts(texts), frame)


def log_only(check: GateCheck | None) -> GateCheck | None:
    """`check`, downgraded so it never asks: hover and scroll only log what they touch."""
    return replace(check, must_confirm=False, asking=frozenset()) if check else None


def form_submit_check(ctx: ActionContext, submits: list[tuple[str, bool]]) -> GateCheck | None:
    """The form-submit rule (send), or None.

    Args:
        ctx: The action context.
        submits: (text, its own form is a sign-in form) for each submit control
            it presses in a form that isn't a search or GET form.
    """
    is_send = any(_is_send_submit(text, in_sign_in_form) for text, in_sign_in_form in submits)
    return ctx.rules.check(CATEGORY_SEND, FORM_SUBMIT_REASON) if is_send else None


def _is_send_submit(text: str, in_sign_in_form: bool) -> bool:
    """False for a save-draft button, or a sign-in button in a sign-in form."""
    if SAVE_DRAFT_RE.match(text):
        return False
    return not (in_sign_in_form and SIGN_IN_WORDING_RE.fullmatch(text))


def key_gate_check(
    ctx: ActionContext, page: Page, key: str, focus: FocusedTarget
) -> GateCheck | None:
    """Which rule a key press on the focused element falls under, or None.

    Off [gates] no_confirm_origins every key that reaches here is at least logged.
    """
    name = key_name(key)
    # Enter submits a form, and so does Space on a submit control.
    is_submit = name in ENTER_KEYS or (name in SPACE_KEYS and focus.is_submit)
    has_submit = is_submit and focus.submit_text is not None
    submits = [(focus.submit_text, focus.in_sign_in_form)] if has_submit else []
    checks = [
        gate_check(ctx, focus.texts, focus.frame_origin),
        form_submit_check(ctx, submits),
        ctx.rules.check(CATEGORY_DELETE, DELETE_KEY_REASON) if name == DELETE_KEY else None,
    ]
    # Unlike the message-box rule, this applies on no_confirm_origins too.
    if is_send_shortcut(key) and not focus.is_search:
        checks.append(ctx.rules.check(CATEGORY_SEND, SEND_SHORTCUT_REASON))
    exempt = {origin_of(origin) for origin in ctx.settings.gates.no_confirm_origins}
    if origin_of(page.url) not in exempt:
        if name in ENTER_KEYS and focus.is_message_box:
            checks.append(ctx.rules.check(CATEGORY_SEND, MESSAGE_BOX_REASON))
        checks.append(ctx.rules.check(None, KEY_PRESS_REASON))
    return strictest(*checks)


async def click_gate_check(
    ctx: ActionContext,
    target: Locator | ElementHandle,
    label: str,
    frame_origin: str | None,
    *,
    scroll_first: bool = True,
) -> GateCheck | None:
    """Which rule clicking (or dragging or dropping on) `target` falls under, or None.

    Args:
        ctx: The action context.
        target: The element the pointer acts on.
        label: Its snapshot label ("" when it has none, e.g. click_at).
        frame_origin: Its frame's origin when that frame is unverified, else None.
        scroll_first: Scroll it into view first, as a click by ref will, so the
            hit test sees the real click point. click_at passes False: its click
            point is fixed on screen, and a scroll would move another element there.
    """
    if scroll_first:
        await target.scroll_into_view_if_needed()
    info = await target.evaluate(ELEMENT_INFO_JS)
    lands_in_frame = (
        ctx.rules.check(None, UNVERIFIED_FRAME_REASON) if info["landsInFrame"] else None
    )
    return strictest(
        gate_check(ctx, [label, info["text"]], frame_origin),
        form_submit_check(ctx, info["submits"]),
        lands_in_frame,
    )


async def select_texts(target: Locator, value: str) -> tuple[str, list[str]]:
    """The select's live name, and the label and value of the option `value` picks.

    Returns:
        (name, [option label, option value]).

    Raises:
        ActionError: If the target (after following a <label>) is not a <select>,
            or no current option matches (Playwright would wait for one to appear).
    """
    found = await target.evaluate(OPTION_TEXTS_JS, value)
    if found is None:
        raise ActionError(NOT_A_DROPDOWN)
    if not found["option"]:
        raise ActionError(NO_SUCH_OPTION)
    return found["name"], found["option"]


async def focused_target(page: Page) -> FocusedTarget:
    """Find the focused element across frames and describe it for gating.

    frame_origin is set when the focused element is in a child frame (an origin
    mismatch, e.g. about:srcdoc).
    """
    for frame in page.frames:
        try:
            found = await frame.evaluate(FOCUSED_TEXTS_JS)
        except PlaywrightError as error:
            logger.debug("skipping frame while reading focus: %s", type(error).__name__)
            continue
        if found is not None:
            frame_origin = None if frame == page.main_frame else origin_of(frame.url)
            return FocusedTarget(frame_origin=frame_origin, **found)
    return FocusedTarget([], None)
