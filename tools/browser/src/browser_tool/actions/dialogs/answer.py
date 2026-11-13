"""The answer_dialog tool: accept or dismiss the confirm, prompt or beforeunload on this tab.

A dialog freezes its tab until it is answered (session.DialogWatch holds it;
every other acting tool refuses the tab meanwhile). The order is the usual one:
the Duo lockout first, then the gate, then guards.ensure_ready_to_act right
before the answer (after_action.act_and_report).

Gating: accepting is gated on the dialog's message plus the texts of the action
that opened it (the clicked button's label, the pressed key and its form), so
an accepted "Delete 3 messages?", or a bare "Are you sure?" after clicking
"Delete", asks the owner as a delete; purchase and send the same way.
Dismissing never asks: it is the cancel button. Right before answering, the
dialog must still be the one the owner judged.

Prompt text: a prompt whose message asks for a password, passcode, PIN or code
gets no text from the model (secrets never pass through it). Typed text is
never logged, nor is the message: logs name only the dialog's kind.
"""

import logging
import re

from playwright.async_api import Page

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.gating import GatedAction, confirm_or_log
from browser_tool.actions.guards import ensure_not_in_duo
from browser_tool.actions.pointer import act_and_report
from browser_tool.policy import origin_of
from browser_tool.session import PendingDialog

logger = logging.getLogger(__name__)

PROMPT = "prompt"
MAX_TEXT_CHARS = 1_000
# A prompt asking for any of these gets no text from the model.
SECRET_PROMPT_RE = re.compile(
    r"pass\s*(word|code|phrase)|passwd|\bpin\b|\bcode\b|\botp\b|one[\s-]?time|2fa|mfa",
    re.IGNORECASE,
)
NO_DIALOG = "no dialog is open on this tab"
OTHER_TAB = "no dialog is open on this tab; tab {index} has one: switch_tab({index}) first"
TEXT_ONLY_PROMPT = "refused: text goes only with accept=true, on a prompt dialog"
TEXT_TOO_LONG = f"refused: text too long (max {MAX_TEXT_CHARS} chars)"
SECRET_PROMPT_REFUSAL = (
    "refused: this prompt asks for a password, passcode, PIN or code, and secrets never "
    "pass through the model. Dismiss it (accept=false) or tell the owner"
)
DIALOG_CHANGED = (
    "refused: the dialog closed or changed while the owner was deciding; nothing was answered"
)


async def answer_dialog(ctx: ActionContext, accept: bool, text: str | None = None) -> str:
    """Accept or dismiss the dialog open on the current tab.

    Args:
        ctx: The action context.
        accept: True presses OK (or Leave), False presses Cancel (or Stay).
        text: For a prompt only, with accept=True: the text to answer with
            (default: the prompt's preset text).

    Returns:
        "accepted/dismissed the <kind> dialog; now at <url>", like a click's result.

    Raises:
        ActionError: If the tab is in Duo, has no dialog, the text is refused,
            the owner declines, or the tab moved meanwhile.
    """
    page = await ctx.session.current_page()
    ensure_not_in_duo(ctx, page)
    pending = _pending_here(ctx, page)
    _check_text(pending, accept, text)
    approved_origin = await _gate_accept(ctx, page, pending, text) if accept else None
    # The re-check: the owner judged this dialog, so it must still be the open one.
    if ctx.session.dialogs.pending(page) is not pending:
        raise ActionError(DIALOG_CHANGED)
    return await _answer(ctx, page, pending, accept, text, approved_origin)


def _pending_here(ctx: ActionContext, page: Page) -> PendingDialog:
    """The current tab's dialog.

    Raises:
        ActionError: NO_DIALOG, or OTHER_TAB naming a tab that has one.
    """
    pending = ctx.session.dialogs.pending(page)
    if pending is not None:
        return pending
    pages = ctx.session.pages()
    for other in ctx.session.dialogs.all_pending():
        if other.page in pages:
            raise ActionError(OTHER_TAB.format(index=pages.index(other.page)))
    raise ActionError(NO_DIALOG)


def _check_text(pending: PendingDialog, accept: bool, text: str | None) -> None:
    """Refuse text off a prompt, too long, or for a prompt asking for a secret.

    Raises:
        ActionError: TEXT_ONLY_PROMPT, TEXT_TOO_LONG or SECRET_PROMPT_REFUSAL.
    """
    if text is None:
        return
    if not accept or pending.kind != PROMPT:
        raise ActionError(TEXT_ONLY_PROMPT)
    if len(text) > MAX_TEXT_CHARS:
        raise ActionError(TEXT_TOO_LONG)
    if SECRET_PROMPT_RE.search(pending.message):
        raise ActionError(SECRET_PROMPT_REFUSAL)


async def _gate_accept(
    ctx: ActionContext, page: Page, pending: PendingDialog, text: str | None
) -> str | None:
    """Run the text rules on the message and its trigger; ask the owner or log.

    Returns:
        The origin the owner approved, or None when nobody was asked.

    Raises:
        ActionError: If the owner declines.
    """
    check = ctx.rules.check_texts([pending.message, *pending.trigger])
    shown = f"accept the {pending.kind} dialog: {pending.message}"
    if text is not None:
        shown += f" (answering: {text})"
    action = GatedAction(shown, f"answer_dialog accept ({pending.kind})", None)
    return await confirm_or_log(ctx, page, action, check)


async def _answer(
    ctx: ActionContext,
    page: Page,
    pending: PendingDialog,
    accept: bool,
    text: str | None,
    approved_origin: str | None,
) -> str:
    """Take the dialog off the watch and answer it; put it back if the last check refuses."""
    watch = ctx.session.dialogs
    is_sent = False

    async def act() -> None:
        nonlocal is_sent
        is_sent = True
        if not accept:
            await pending.dialog.dismiss()
        elif pending.kind == PROMPT:
            await pending.dialog.accept(pending.default_value if text is None else text)
        else:
            await pending.dialog.accept()

    verb = "accepted" if accept else "dismissed"
    # Off the watch first: ensure_ready_to_act refuses a tab with a dialog held.
    watch.take(page)
    try:
        # The message is kept as a trigger: a follow-up "Are you sure?" is gated on it.
        result = await act_and_report(
            ctx,
            page,
            approved_origin,
            act,
            f"{verb} the {pending.kind} dialog",
            trigger=[*pending.trigger, pending.message],
        )
    except ActionError:
        if not is_sent:
            watch.restore(pending)
        raise
    logger.info("answer_dialog: %s a %s dialog on %s", verb, pending.kind, origin_of(page.url))
    return result
