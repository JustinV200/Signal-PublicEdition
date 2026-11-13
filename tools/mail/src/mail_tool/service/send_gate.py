"""SendGate: asks the owner, in the shared signal_confirm Allow/Deny dialog, before a draft is sent.

The dialog lists every recipient's bare address on its own line, in full,
right below the account (see recipients.py). Then it shows the subject and as
many body lines as fit. Untrusted text is flattened by sanitize_text, so it
can't fake extra lines. The whole text is kept under the dialog's own length
limit, because past that limit the dialog would elide the middle, where the
recipients are. Deny is the default, Allow needs a mouse click, and no answer
within the timeout counts as Deny.
"""

import logging
from collections.abc import Callable
from typing import Any

from signal_confirm import confirm, sanitize_text

from mail_tool.auth import AccountRecord
from mail_tool.errors import SendRefused
from mail_tool.gmail import extract_content, header_map
from mail_tool.service.recipients import MAX_ADDRESS_CHARS, Recipient, draft_recipients

logger = logging.getLogger(__name__)

DIALOG_TITLE = "Signal mail: send this email?"
CONFIRM_TIMEOUT_S = 120
PREVIEW_LINES = 6
MAX_LINE_CHARS = 120
# signal_confirm's dialog elides the middle of messages longer than this (dialog.MAX_MESSAGE_CHARS).
MAX_DIALOG_CHARS = 2000
# Room kept for the "... (N more lines)" note or "(empty body)" after the preview.
PREVIEW_NOTE_RESERVE_CHARS = 40

# (title, message, *, timeout_s) -> True only for Allow. The real one is signal_confirm.confirm.
AskOwner = Callable[..., bool]


def confirm_text(
    record: AccountRecord, message: dict[str, Any], recipients: list[Recipient]
) -> str:
    """The dialog body for sending `message` (a format=full draft message) from `record`.

    Raises:
        SendRefused: The recipients alone don't fit in the dialog.
    """
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    head = [
        "Claude wants to send this email.",
        "",
        f"Account: {record.alias} ({record.email})",
        f"Recipients ({len(recipients)}), each address in full:",
    ]
    # No elision: draft_recipients already refused any address longer than this.
    head += [f"{r.kind}: {sanitize_text(r.address, MAX_ADDRESS_CHARS)}" for r in recipients]
    head += [f"Subject: {_line(header_map(payload).get('subject', '')) or '(none)'}", ""]
    tail = [
        "",
        "Only click Allow if you want exactly this sent.",
        f"Deny is the default. This denies itself after {CONFIRM_TIMEOUT_S} seconds.",
    ]
    fixed_chars = len("\n".join(head + tail)) + PREVIEW_NOTE_RESERVE_CHARS
    if fixed_chars > MAX_DIALOG_CHARS:
        raise SendRefused("The recipient list is too long to show the owner, so it was not sent.")
    body_lines = [line for line in extract_content(payload).text.splitlines() if line.strip()]
    preview = _fit_preview(body_lines, MAX_DIALOG_CHARS - fixed_chars)
    return "\n".join(head + preview + tail)


class SendGate:
    """Decides whether a draft may be sent: the owner's click, or config send.confirm = false."""

    def __init__(self, is_enabled: bool, ask: AskOwner = confirm) -> None:
        """Args: is_enabled: config send.confirm; ask: the dialog (signal_confirm.confirm)."""
        self._is_enabled = is_enabled
        self._ask = ask

    def check(self, record: AccountRecord, message: dict[str, Any]) -> None:
        """Return only if sending is allowed. Blocks while the dialog is open.

        The recipient checks apply even with send.confirm off.

        Raises:
            SendRefused: Unreadable or too many recipients, or the owner didn't click Allow.
        """
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        recipients = draft_recipients(payload)
        if not self._is_enabled:
            logger.warning("send.confirm is false: sending a draft from %s unasked", record.alias)
            return
        text = confirm_text(record, message, recipients)
        if not self._ask(DIALOG_TITLE, text, timeout_s=CONFIRM_TIMEOUT_S):
            raise SendRefused("The owner didn't approve sending this draft, so it was not sent.")


def _fit_preview(body_lines: list[str], budget_chars: int) -> list[str]:
    """The first body lines (sanitized) that fit in budget_chars, then a note on what's left out.

    The note (or "(empty body)") fits in PREVIEW_NOTE_RESERVE_CHARS, outside the budget.
    """
    if not body_lines:
        return ["(empty body)"]
    preview: list[str] = []
    used = 0
    for line in (_line(text) for text in body_lines[:PREVIEW_LINES]):
        if used + len(line) + 1 > budget_chars:
            break
        preview.append(line)
        used += len(line) + 1
    omitted = len(body_lines) - len(preview)
    return preview + [f"... ({omitted} more lines)"] if omitted else preview


def _line(text: str) -> str:
    """One capped, flattened line of untrusted text."""
    return sanitize_text(text, MAX_LINE_CHARS)
