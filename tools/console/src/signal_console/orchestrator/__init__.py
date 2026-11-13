"""Public API of signal_console.orchestrator: claim a session, word chats, send to its inbox.

The claim type and the inbox sender come from the shared signal_orchestrator
package (the voice hub sends through it too); they're re-exported here so the
rest of the console imports everything orchestrator-related from one place.
"""

from signal_orchestrator import (
    SOCKET_ENV,
    Claim,
    ClaimError,
    InboxError,
    claim_from_env,
    encode_frames,
    send_to_inbox,
)

from signal_console.orchestrator.claim import read_claim, write_claim
from signal_console.orchestrator.messages import (
    MARKER,
    ConsoleRequest,
    RequestError,
    chat_request,
)

__all__ = [
    "MARKER",
    "SOCKET_ENV",
    "Claim",
    "ClaimError",
    "ConsoleRequest",
    "InboxError",
    "RequestError",
    "chat_request",
    "claim_from_env",
    "encode_frames",
    "read_claim",
    "send_to_inbox",
    "write_claim",
]
