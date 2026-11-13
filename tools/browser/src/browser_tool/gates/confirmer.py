"""The owner-confirmation interface for sensitive browser actions.

A Confirmer asks the human owner, out of band from the model, whether an action
may proceed. No MCP tool can answer it: the tool call simply waits for the
owner's yes/no. Known limit: the model's shell runs as the same Windows user, so a
same-user process could in principle script the dialog. Implementations:
DialogConfirmer (the signal_confirm Allow/Deny dialog) now; an audiohub spoken yes/no later.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ConfirmationRequest:
    """What the owner is asked to approve.

    Attributes:
        action: What will happen, e.g. 'click button "Buy now"' (page-supplied text).
        origin: The top-level page origin, from the browser, e.g. "https://shop.example".
        reason: Why it needs approval, e.g. "matches a purchase/send/delete rule".
        frame_origin: The element's frame origin when it differs from `origin`
            (e.g. "about:srcdoc"), else None.
        job: The browser job the action runs in (e.g. "docker job 1a2b3c"), or
            None for the desktop browser.
    """

    action: str
    origin: str
    reason: str
    frame_origin: str | None = None
    job: str | None = None


class Confirmer(Protocol):
    """Asks the owner to approve one action."""

    async def confirm(self, request: ConfirmationRequest) -> bool:
        """Return True only if the owner explicitly approved. Timeouts mean False."""
        ...
