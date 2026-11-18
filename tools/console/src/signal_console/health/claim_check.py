"""The claim row: is a Claude Code session linked, is it still open, and how old is the claim?

Liveness is orchestrator.is_claim_alive (the session's inbox pipe is listed;
nothing connects to it). The row names the claim's label and age, never its
socket or token.
"""

from datetime import datetime

from signal_console.health.inputs import HealthPaths
from signal_console.health.row import ATTENTION, OK, HealthRow
from signal_console.orchestrator import claimed_ago, is_claim_alive, read_claim
from signal_console.paths import CLAIM_FILE

# Runs from the repo root, which is where Claude Code's Bash tool starts.
CLAIM_COMMAND = "uv run --project tools/console --frozen --no-sync console claim"
CLAIM_FIX = "In your main Claude Code session, have Claude run this with its Bash tool."


def claim_row(paths: HealthPaths, now: datetime) -> HealthRow:
    """The claim's state: linked and open (ok), closed, damaged or missing (attention).

    Args:
        paths: Where the claim file is (state_dir).
        now: The current time, timezone-aware (for the claim's age).
    """
    claim = read_claim(paths.state_dir)
    if claim is None:
        is_damaged = (paths.state_dir / CLAIM_FILE).exists()
        state = "unreadable" if is_damaged else "none"
        words = (
            "The claim file can't be read, so no Claude Code session is linked."
            if is_damaged
            else "No Claude Code session is linked to the console yet."
        )
        return HealthRow(
            "claim", "Claude session", ATTENTION, state, words, CLAIM_FIX, CLAIM_COMMAND
        )
    named = f' "{claim.label}"' if claim.label else ""
    age = claimed_ago(claim.claimed_at, now)
    aged = f" ({age})" if age else ""
    if is_claim_alive(claim):
        words = f"Claude Code session{named} is open{aged}."
        return HealthRow("claim", "Claude session", OK, "linked", words)
    words = f"The session{named}{aged} has closed, so messages can't reach Claude."
    return HealthRow(
        "claim", "Claude session", ATTENTION, "closed", words, CLAIM_FIX, CLAIM_COMMAND
    )
