"""ChangeGate: asks the owner (shared signal_confirm dialog) before touching others' events.

Events the tool created (its private marker) pass without asking. Any other
event's update, delete or reply opens the Allow/Deny dialog with the event's
title, time and calendar, whether it has guests, and exactly what will change,
every new value in full. The whole text is kept under the dialog's own length
limit, because past it the dialog would cut the middle and hide part of the new
text, so a change too long to show in full is refused before asking.
`[changes] confirm = false` turns the dialog off for single events, but a
whole-series change to an event the tool didn't create always asks. Event text
comes from whoever sent the invite, so every line is flattened by sanitize_text
and can't fake extra lines. Deny is the default, Allow needs a mouse click, and
no answer within the timeout counts as Deny. This is a human gate, not a sandbox
(see packages/confirm).
"""

import logging
from collections.abc import Callable
from datetime import tzinfo

from signal_confirm import confirm, sanitize_text

from calendar_tool.agenda import NO_TITLE
from calendar_tool.changes.target import Target
from calendar_tool.changes.times import describe_span
from calendar_tool.errors import ChangeRefused
from calendar_tool.google_api import has_guests, is_recurring

logger = logging.getLogger(__name__)

DIALOG_TITLE = "Signal calendar: change this event?"
CONFIRM_TIMEOUT_S = 120
# Caps the event's own lines (title, calendar). Change lines aren't capped: new text shows whole.
MAX_LINE_CHARS = 160
# signal_confirm's dialog elides the middle of messages longer than this (dialog.MAX_MESSAGE_CHARS).
MAX_DIALOG_CHARS = 2000
# New title, location and description together that always fit: the rest of the
# dialog measured 1094 characters at worst (a long title and calendar name, a whole
# series with guests, and every field changed at once), leaving 906.
MAX_NEW_TEXT_CHARS = 850
REFUSED = "The owner didn't approve this change, so nothing was changed."
TOO_LONG = (
    f"This change is too long to show the owner in full (the dialog holds {MAX_DIALOG_CHARS} "
    f"characters; keep a new title, location and description under {MAX_NEW_TEXT_CHARS} "
    "together), so nothing was changed."
)
# No email isn't no effect: an organizer's change reaches every guest's copy.
GUESTS_LINE = (
    "Guests: other people are on this event, and their copies may show this change "
    "even when Google sends no email."
)

# (title, message, *, timeout_s) -> True only for Allow. The real one is signal_confirm.confirm.
AskOwner = Callable[..., bool]


def dialog_text(target: Target, changes: list[str], zone: tzinfo | None = None) -> str:
    """The dialog body: the event as it is now, then each change on its own line.

    Raises:
        ApiError: The event's start can't be read.
    """
    raw = target.raw
    lines = [
        "Claude wants to change an event it didn't create.",
        "",
        f"Event: {_line(raw.get('summary') or NO_TITLE)}",
        f"When: {describe_span(raw.get('start'), raw.get('end'), zone)}",
        f"Calendar: {_line(target.calendar.name)}",
    ]
    if target.is_series:
        lines.append("Applies to: EVERY occurrence of this repeating event")
    elif is_recurring(raw):
        lines.append("Applies to: this occurrence only")
    if has_guests(raw):
        lines.append(GUESTS_LINE)
    # Flattened but not capped: the owner must see every new value whole.
    lines += ["", *(f"Change: {sanitize_text(change, len(change))}" for change in changes), ""]
    lines += [
        "Only click Allow if you want exactly this change.",
        f"Deny is the default. This denies itself after {CONFIRM_TIMEOUT_S} seconds.",
    ]
    return "\n".join(lines)


class ChangeGate:
    """Decides whether a change may go ahead: the tool's own event, the owner's click, or config."""

    def __init__(
        self, is_enabled: bool, ask: AskOwner = confirm, zone: tzinfo | None = None
    ) -> None:
        """Args: is_enabled: config changes.confirm; ask: the dialog; zone: for the times shown."""
        self._is_enabled = is_enabled
        self._ask = ask
        self._zone = zone

    def check(self, target: Target, changes: list[str]) -> None:
        """Return only if the change may be made. Blocks while the dialog is open.

        Args:
            target: The event as just re-read.
            changes: What will change, one line each (e.g. "delete this event").

        Raises:
            ChangeRefused: The change is too long to show in full, or the owner didn't click Allow.
        """
        if target.is_mine:
            return
        if not self._is_enabled and not target.is_series:
            logger.warning("changes.confirm is false: changing an event the tool didn't create")
            return
        text = dialog_text(target, changes, self._zone)
        # Lines are already flattened, so the dialog's sanitize_message can only shorten this.
        if len(text) > MAX_DIALOG_CHARS:
            raise ChangeRefused(TOO_LONG)
        if not self._ask(DIALOG_TITLE, text, timeout_s=CONFIRM_TIMEOUT_S):
            raise ChangeRefused(REFUSED)


def _line(text: object) -> str:
    """One capped, flattened line of possibly untrusted text."""
    return sanitize_text(str(text), MAX_LINE_CHARS)
