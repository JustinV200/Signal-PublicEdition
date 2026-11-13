"""Public API of signal_orchestrator: read the orchestrator's claim and send to its inbox.

The console (tools/console) writes the claim and sends the owner's typed requests;
the voice hub (tools/audiohub) sends hand-offs. Both use this one sender.
Test helpers live in signal_orchestrator.testing and aren't re-exported here.
"""

from signal_orchestrator.claim import (
    SOCKET_ENV,
    TOKEN_ENV,
    Claim,
    ClaimError,
    claim_from_env,
    claim_to_json,
    read_claim_file,
)
from signal_orchestrator.inbox import InboxError, encode_frames, send_to_inbox

__all__ = [
    "SOCKET_ENV",
    "TOKEN_ENV",
    "Claim",
    "ClaimError",
    "InboxError",
    "claim_from_env",
    "claim_to_json",
    "encode_frames",
    "read_claim_file",
    "send_to_inbox",
]
