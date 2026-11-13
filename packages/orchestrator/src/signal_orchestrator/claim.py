"""The claim: which Claude Code session is the Signal orchestrator, and where its inbox is.

`console claim` (tools/console), run from the orchestrator's own Bash or
PowerShell tool, inherits that session's inbox address and token (Claude Code
exports both to its tools) and saves them as a JSON file. The console and the
voice hub read that file to message the orchestrator. This module builds,
encodes and checks claims; where the file lives, and locking it to the owner,
are the console's job.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SOCKET_ENV = "CLAUDE_CODE_MESSAGING_SOCKET"
TOKEN_ENV = "CLAUDE_CODE_MESSAGING_TOKEN"
# Only a Windows named pipe is supported (see inbox.py).
PIPE_PREFIX = "\\\\.\\pipe\\"
MAX_LABEL_CHARS = 80


class ClaimError(ValueError):
    """The environment has no usable inbox to claim."""


@dataclass(frozen=True)
class Claim:
    """A claimed orchestrator session's inbox.

    Attributes:
        socket: Its inbox named pipe, e.g. \\\\.\\pipe\\LOCAL\\cc-msg-<hex>.
        token: Its CLAUDE_CODE_MESSAGING_TOKEN; sent as the auth line, it makes
            our messages count as the session's own (delivered without approval).
        label: Optional name shown in the console.
        claimed_at: When it was claimed (UTC ISO).
    """

    socket: str
    # Kept out of repr, so a logged or printed claim never shows the token.
    token: str = field(repr=False)
    label: str | None
    claimed_at: str


def claim_from_env(environ: Mapping[str, str], label: str | None) -> Claim:
    """Build a claim from the calling session's exported inbox variables.

    Raises:
        ClaimError: The variables are missing or don't look like a named-pipe inbox.
    """
    socket = environ.get(SOCKET_ENV, "")
    token = environ.get(TOKEN_ENV, "").strip()
    if not _is_pipe_address(socket) or not token:
        raise ClaimError(
            f"{SOCKET_ENV} and {TOKEN_ENV} aren't set to a named-pipe inbox; run "
            "`console claim` from the orchestrator session's own Bash or PowerShell tool"
        )
    label = (label or "").strip()[:MAX_LABEL_CHARS] or None
    return Claim(socket, token, label, datetime.now(UTC).isoformat(timespec="seconds"))


def claim_to_json(claim: Claim) -> dict[str, Any]:
    """The claim as the JSON object the claim file holds (token included: keep it private)."""
    return {
        "socket": claim.socket,
        "token": claim.token,
        "label": claim.label,
        "claimedAt": claim.claimed_at,
    }


def read_claim_file(path: Path) -> Claim | None:
    """The claim saved at `path`, or None if it's missing, unreadable or malformed.

    Its socket is checked again, as claim_from_env checked it: the token is
    written to whatever it names, so a file or UNC path is refused.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    socket, token, label = payload.get("socket"), payload.get("token"), payload.get("label")
    if not isinstance(socket, str) or not _is_pipe_address(socket):
        return None
    if not isinstance(token, str) or not token:
        return None
    return Claim(
        socket,
        token,
        label if isinstance(label, str) else None,
        str(payload.get("claimedAt", "")),
    )


def _is_pipe_address(socket: str) -> bool:
    # Windows still resolves ".." (with "/" as a separator) in \\.\ paths, so
    # \\.\pipe\..\C:\x would open the file \\.\C:\x; refuse both, not just the prefix.
    return socket.startswith(PIPE_PREFIX) and ".." not in socket and "/" not in socket
