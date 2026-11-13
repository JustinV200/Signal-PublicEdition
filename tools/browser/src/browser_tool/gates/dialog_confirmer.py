"""A Confirmer that asks the owner in the shared signal_confirm Allow/Deny dialog.

The dialog runs in its own child process (packages/confirm), so the event loop
keeps serving the browser while it waits. Deny is the default, Allow has no
keyboard shortcut, and an unanswered dialog denies by itself after the timeout.
Dialogs are shown one at a time.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from signal_confirm import confirm_async

from browser_tool.gates.confirmer import ConfirmationRequest
from browser_tool.redaction import replace_unsafe_chars

logger = logging.getLogger(__name__)

DIALOG_TITLE = "Signal browser: confirm action"
MAX_ACTION_CHARS = 160

# (title, message, *, timeout_s) -> approved? The real one is signal_confirm.confirm_async.
ShowDialog = Callable[..., Awaitable[bool]]


def build_dialog_text(request: ConfirmationRequest) -> str:
    """Compose the dialog body: the action, the origin and why it is gated."""
    # Page-supplied text: no fake extra lines, bidi reversal or hidden characters.
    action = replace_unsafe_chars(request.action, " ")
    if len(action) > MAX_ACTION_CHARS:
        action = action[:MAX_ACTION_CHARS] + "..."
    intro = "Claude wants to do something that needs your OK."
    lines = [
        f"{request.job}: {intro}" if request.job else intro,
        "",
        f"Action:  {action}",
        f"Site:    {request.origin}",
    ]
    if request.frame_origin:
        lines.append(f"Frame:   {replace_unsafe_chars(request.frame_origin, ' ')}")
    lines += [f"Why:     {request.reason}", "", "Allow it?"]
    return "\n".join(lines)


class DialogConfirmer:
    """Confirmer backed by the signal_confirm Allow/Deny dialog."""

    def __init__(self, timeout_s: float, show_dialog: ShowDialog = confirm_async):
        """Create the confirmer.

        Args:
            timeout_s: Seconds before an unanswered dialog counts as "Deny".
            show_dialog: The async dialog function; tests pass a fake.
        """
        self._timeout_s = timeout_s
        self._show_dialog = show_dialog
        self._one_at_a_time = asyncio.Lock()

    async def confirm(self, request: ConfirmationRequest) -> bool:
        """Show the dialog and return True only for an explicit "Allow"."""
        text = build_dialog_text(request)
        async with self._one_at_a_time:
            is_approved = await self._show_dialog(DIALOG_TITLE, text, timeout_s=self._timeout_s)
        logger.info(
            "owner %s: %s on %s",
            "approved" if is_approved else "declined",
            request.reason,
            request.origin,
        )
        return is_approved
