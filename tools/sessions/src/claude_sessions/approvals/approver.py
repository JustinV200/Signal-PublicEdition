"""The Approver interface: how a managed session asks the owner whether a tool call may run.

The daemon builds an ApprovalRequest for each tool call the CLI would prompt
for and awaits an Approver. The real one is DialogApprover (the topmost
signal_confirm Allow/Deny dialog); tests pass a fake. Approvers must always return eventually
(they own their timeout) and should deny when in doubt.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol


def _nothing() -> None:
    """Default on_shown: no one to tell."""


@dataclass(frozen=True)
class ApprovalRequest:
    """One tool call waiting for the owner's yes or no.

    Attributes:
        session_id: The managed session asking.
        repo_name: The repo the session runs in, e.g. "OtherRepo".
        tool_name: The tool, e.g. "Bash".
        description: A short human description of the call (see describe_tool_call).
        on_shown: Called once, just as the owner is actually asked (not while the
            request waits behind another dialog); the session posts its voice note here.
    """

    session_id: str
    repo_name: str
    tool_name: str
    description: str
    on_shown: Callable[[], None] = field(default=_nothing, compare=False, repr=False)


class Approver(Protocol):
    """Decides tool calls for managed sessions."""

    async def approve(self, request: ApprovalRequest) -> bool:
        """Ask whether the call may run.

        Args:
            request: The call to decide.

        Returns:
            True to allow it, False to deny it (including on timeout).
        """
        ...
