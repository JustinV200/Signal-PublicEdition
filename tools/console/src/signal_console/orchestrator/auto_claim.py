"""Auto-claim: `console tasks set` links its caller when no open session holds the claim.

The orchestrator runs `console tasks set` early in every task (AGENTS.md
section 3), so a new session after a handoff or a restart takes over a claim
that is missing or whose session has closed, without a separate
`console claim`. A live claim is never replaced here; only an explicit
`console claim` does that, and a claim whose session can't be checked (the
pipe list can't be read) is left alone too. The claim goes through write_claim, like
`console claim`, so the status watcher notes the takeover in the feed.

Subagents run inside their parent's Claude Code process and their tools get
the same inbox variables, so a subagent's `tasks set` claims for its parent
session, never for itself. A process with no inbox variables (a plain
terminal) claims nothing and its `tasks set` still works.
"""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from signal_orchestrator import Claim, ClaimError, claim_from_env

from signal_console.orchestrator.claim import read_claim, write_claim
from signal_console.orchestrator.claim_words import default_label
from signal_console.orchestrator.liveness import claim_pipe_listed


def claim_if_free(state_dir: Path, environ: Mapping[str, str], now: datetime) -> Claim | None:
    """Claim the console for the session in `environ` if no open session holds it.

    Args:
        state_dir: The console's .state folder (tests pass a temp one).
        environ: The caller's environment, holding its inbox variables.
        now: When it runs; a new claim is labelled with its local time.

    Returns:
        The new claim, or None when an open session already holds the claim,
        the held claim's session can't be checked, or `environ` has no inbox
        to claim.

    Raises:
        OSError: The claim file couldn't be locked or written.
    """
    held = read_claim(state_dir)
    # Replace only a claim known to be closed: "can't tell" (None) may be a live one.
    if held is not None and claim_pipe_listed(held) is not False:
        return None
    try:
        claim = claim_from_env(environ, default_label(now))
    except ClaimError:
        # Not run from a Claude Code session's tool: nothing to claim, by design.
        return None
    write_claim(state_dir, claim)
    return claim
