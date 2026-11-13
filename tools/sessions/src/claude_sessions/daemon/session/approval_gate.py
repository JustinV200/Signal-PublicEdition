"""ApprovalGate: routes one session's tool-call approvals to the Approver and tracks the wait.

While any approval is pending the session shows "awaiting_permission" (with
the call's description in status). A high-priority voice note tells the owner
to look at the dialog when that call's dialog is actually shown, not while it
waits behind another one. Once the last pending call is answered the
session is back to "working".
"""

from collections.abc import Callable

from signal_hub_notify import Notifier

from claude_sessions.approvals import ApprovalRequest, Approver, describe_tool_call
from claude_sessions.daemon.session.record import SessionRecord, SessionState
from claude_sessions.notify import approval_needed_note
from claude_sessions.sdk import ToolCall


class ApprovalGate:
    """Decides tool calls for one managed session by asking the Approver."""

    def __init__(
        self,
        record: SessionRecord,
        approver: Approver,
        notifier: Notifier,
        set_state: Callable[[SessionState], None],
    ) -> None:
        """Create the gate.

        Args:
            record: The session's record (read for ids, names and the current state).
            approver: Asks the owner.
            notifier: Announces that a call is waiting.
            set_state: Changes and persists the session's state.
        """
        self._record = record
        self._approver = approver
        self._notifier = notifier
        self._set_state = set_state
        # The SDK runs each permission request in its own task, so several can overlap.
        self._pending_descriptions: list[str] = []

    @property
    def pending_description(self) -> str | None:
        """The oldest call still waiting for an answer, or None."""
        return self._pending_descriptions[0] if self._pending_descriptions else None

    async def decide(self, call: ToolCall) -> bool:
        """Ask the owner about one call. Matches sdk.ToolCallDecider.

        Args:
            call: The tool call the CLI wants approved.

        Returns:
            The Approver's answer. Errors propagate; make_can_use_tool denies on them.
        """
        description = describe_tool_call(call.tool_name, call.tool_input, call.title)
        self._pending_descriptions.append(description)
        self._set_state(SessionState.AWAITING_PERMISSION)
        note = approval_needed_note(self._record.repo_name, description)
        request = ApprovalRequest(
            session_id=self._record.id,
            repo_name=self._record.repo_name,
            tool_name=call.tool_name,
            description=description,
            on_shown=lambda: self._notifier.post(note),
        )
        try:
            return await self._approver.approve(request)
        finally:
            self._pending_descriptions.remove(description)
            # A stop while waiting leaves the session stopped, not working.
            if (
                not self._pending_descriptions
                and self._record.state is SessionState.AWAITING_PERMISSION
            ):
                self._set_state(SessionState.WORKING)
