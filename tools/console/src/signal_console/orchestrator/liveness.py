"""Is the claimed Claude Code session still open? Told by its inbox pipe's name alone.

A session's inbox is a named pipe that exists only while the session runs, so
a claim whose pipe isn't listed under \\\\.\\pipe\\ belongs to a closed session.
Nothing connects to the pipe: the session never sees a probe and the token is
never sent. The status watcher uses this for `orchestrator.alive` and the
auto-claim in `console tasks set` to spot a closed claim (claim_pipe_listed,
which also reports "can't tell"); the doctor is meant to share it.
"""

import logging
from os import listdir

from signal_orchestrator import PIPE_PREFIX, Claim

log = logging.getLogger(__name__)


def is_claim_alive(claim: Claim | None) -> bool:
    """True when `claim` names a session whose inbox pipe exists now.

    No claim is never alive. Listing the pipes takes about a millisecond (600
    pipes on the owner's PC), cheap enough for every status poll.

    Args:
        claim: The saved claim, or None when there is none.

    Returns:
        Whether its pipe is listed. Never raises: when the pipes can't be
        listed (not Windows), the claim counts as closed and a warning is logged.
    """
    if claim is None:
        return False
    # An unknown answer (None) counts as closed here.
    return claim_pipe_listed(claim) is True


def claim_pipe_listed(claim: Claim) -> bool | None:
    """Whether `claim`'s inbox pipe is listed now, or None when that can't be told.

    For callers that must not treat "can't tell" as closed, like the
    auto-claim, which must never replace a live claim.

    Args:
        claim: The saved claim.

    Returns:
        True or False from the pipe listing, or None when the pipes can't be
        listed (not Windows); a warning is logged then. Never raises.
    """
    try:
        names = listdir(PIPE_PREFIX)
    except OSError as error:
        log.warning("can't list named pipes (%s), so the claim's session can't be checked", error)
        return None
    # Pipe names ignore case on Windows; the listing drops the \\.\pipe\ prefix.
    wanted = claim.socket.removeprefix(PIPE_PREFIX).casefold()
    return any(name.casefold() == wanted for name in names)
