"""DialogApprover: the default Approver, asking the owner in the shared signal_confirm dialog.

One dialog is shown at a time, so parallel tool calls (or several sessions)
don't stack dialogs on top of each other; each waits its turn. The timeout
covers the whole wait, queue included: a call still queued when it runs out is
denied without a dialog, and a dialog only gets the time that is left. The dialog runs
in its own child process (packages/confirm), so the daemon's event loop keeps
serving IPC and reading other sessions meanwhile.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from signal_confirm import confirm_async

from claude_sessions.approvals.approver import ApprovalRequest
from claude_sessions.config import DEFAULT_APPROVAL_TIMEOUT_S

logger = logging.getLogger(__name__)

TITLE_PREFIX = "Claude session"
# Extra time past the approval timeout for the dialog's own deny to arrive
# before the whole wait is cut off (the dialog child needs a moment to start).
DIALOG_GRACE_S = 5.0
# A queued call with less time than this left is denied instead of flashing a dialog.
MIN_DIALOG_S = 1.0

# (title, text, *, timeout_s) -> True for Allow. The real one is signal_confirm.confirm_async.
ShowDialog = Callable[..., Awaitable[bool]]


class DialogApprover:
    """Asks the owner about each tool call with an Allow/Deny dialog that defaults to Deny."""

    def __init__(
        self,
        timeout_s: float = DEFAULT_APPROVAL_TIMEOUT_S,
        show_dialog: ShowDialog = confirm_async,
    ) -> None:
        """Configure the approver.

        Args:
            timeout_s: Seconds a call may wait in all, queue included, before it is denied.
            show_dialog: Shows one dialog and awaits the answer; tests pass a
                fake. Defaults to signal_confirm.confirm_async.
        """
        self._timeout_s = timeout_s
        self._show_dialog = show_dialog
        self._dialog_lock = asyncio.Lock()

    async def approve(self, request: ApprovalRequest) -> bool:
        """Show the dialog for one request and return the owner's answer.

        Args:
            request: The tool call to decide.

        Returns:
            True only for Allow. Deny, the timeout (queue included), and any
            failure to show the dialog all deny (failing closed).
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._timeout_s
        try:
            async with asyncio.timeout_at(deadline + DIALOG_GRACE_S), self._dialog_lock:
                is_allowed = await self._ask(request, deadline - loop.time())
        except TimeoutError:
            logger.warning("Approval for %s timed out; denying", request.tool_name)
            return False
        logger.info(
            "Owner %s %s for %s",
            "allowed" if is_allowed else "denied",
            request.tool_name,
            request.session_id,
        )
        return is_allowed

    async def _ask(self, request: ApprovalRequest, remaining_s: float) -> bool:
        """Show the dialog with the time left (lock held); deny when too little is left."""
        if remaining_s < MIN_DIALOG_S:
            logger.info("Approval for %s ran out of time in the queue", request.tool_name)
            return False
        request.on_shown()
        title = f"{TITLE_PREFIX}: {request.repo_name}"
        text = _dialog_text(request, remaining_s)
        try:
            return await self._show_dialog(title, text, timeout_s=remaining_s)
        except Exception:
            logger.exception("Couldn't show the approval dialog; denying %s", request.tool_name)
            return False


def _dialog_text(request: ApprovalRequest, timeout_s: float) -> str:
    """The question shown in the dialog body."""
    return (
        f"The Claude session in {request.repo_name} ({request.session_id}) wants to:\n\n"
        f"{request.description}\n\n"
        f"Allow it? Deny is the default, and the call is denied after {timeout_s:.0f} seconds."
    )
