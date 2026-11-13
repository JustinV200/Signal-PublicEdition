"""The `Confirmer` interface: asks the owner, directly, whether one specific fill may happen.

The vault runs the confirmer itself; the model never relays the answer. The
native dialog is the v1 implementation; an audiohub voice confirmer can be
added behind the same interface once audiohub has a confirm endpoint.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ConfirmRequest:
    """What the owner is asked to approve.

    Attributes:
        credential_id: The stored credential's id.
        credential_name: Its display name.
        top_origin: The live origin of the top-level page.
        frame_origin: The live origin of the frame holding the password field
            (equal to top_origin unless the form is in an iframe).
    """

    credential_id: str
    credential_name: str
    top_origin: str
    frame_origin: str


class Confirmer(Protocol):
    """Gets an explicit yes/no from the owner. Anything but a clear yes is a no."""

    async def confirm(self, request: ConfirmRequest) -> bool:
        """Return True only if the owner approved this fill."""
        ...
