"""The dialog and file-picker notes the tool runner adds to every result.

Each result says which alerts were shown (and accepted) since the last one,
which tabs opened a file picker of their own (intercepted and dropped), and,
for as long as one is open, every confirm, prompt or beforeunload and how to
answer it. Messages are page text: they go inside <untrusted_page_content>,
on one line, and through the tool runner's scrub with the rest of the result.
"""

from playwright.async_api import Page

from browser_tool.actions.context import ActionContext
from browser_tool.actions.untrusted import wrap_untrusted
from browser_tool.redaction import replace_unsafe_chars
from browser_tool.session import PendingDialog

ALERT_NOTE = "{tab} showed an alert, which was accepted: {message}"
MORE_ALERTS_NOTE = "and {count} more alerts, also accepted"
PICKER_NOTE = (
    "{tab} opened a file picker, which was closed without a file; to upload one, "
    "use upload_file(ref, path) on the upload button or file input"
)
PENDING_NOTE = "a {kind} dialog is open on {tab}, and the page waits for it: {message}"
PROMPT_HINT = "; it asks for text (preset: {preset}); answer with answer_dialog(accept, text)"
LEAVE_HINT = "; accept leaves the page, dismiss stays"
ANSWER_HINT = "; answer it with answer_dialog(accept=true or false)"


def dialog_notes(ctx: ActionContext) -> list[str]:
    """The notes for this result: alerts and pickers since the last one, and open dialogs."""
    pages = ctx.session.pages()

    def tab(page: Page) -> str:
        return f"tab {pages.index(page)}" if page in pages else "a closed tab"

    alerts, more_alerts = ctx.session.dialogs.take_alerts()
    notes = [
        ALERT_NOTE.format(tab=tab(alert.page), message=_shown(alert.message)) for alert in alerts
    ]
    if more_alerts:
        notes.append(MORE_ALERTS_NOTE.format(count=more_alerts))
    notes += [PICKER_NOTE.format(tab=tab(page)) for page in ctx.session.file_choosers.take_opened()]
    notes += [_pending_note(tab(found.page), found) for found in ctx.session.dialogs.all_pending()]
    return notes


def _pending_note(tab: str, pending: PendingDialog) -> str:
    """How an open dialog is described, with how to answer it."""
    note = PENDING_NOTE.format(kind=pending.kind, tab=tab, message=_shown(pending.message))
    if pending.kind == "prompt":
        return note + PROMPT_HINT.format(preset=_shown(pending.default_value))
    if pending.kind == "beforeunload":
        note += LEAVE_HINT
    return note + ANSWER_HINT


def _shown(text: str) -> str:
    """Page text on one line, inside the untrusted wrapper."""
    return wrap_untrusted(replace_unsafe_chars(text, " "))
