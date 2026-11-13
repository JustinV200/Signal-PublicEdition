"""The console's claim file: which Claude Code session is the orchestrator it talks to.

`console claim`, run from the orchestrator's own Bash or PowerShell tool,
inherits that session's inbox address and token and saves them to
.state/orchestrator.json, owner-only. The server sends to that inbox, the
turn hook only reports turns of that session, and the voice hub reads the
same file to hand jobs off. A successor orchestrator after a handoff runs
`console claim` again. Building and checking a claim is the shared
signal_orchestrator package's job; this module only places and locks the file.
"""

from pathlib import Path

from signal_orchestrator import Claim, claim_to_json, read_claim_file

from signal_console.paths import CLAIM_FILE
from signal_console.state_files import write_json


def write_claim(state_dir: Path, claim: Claim) -> None:
    """Save the claim to .state/orchestrator.json, readable by the owner only.

    Raises:
        OSError: The file couldn't be locked or written.
    """
    write_json(state_dir / CLAIM_FILE, claim_to_json(claim), is_private=True)


def read_claim(state_dir: Path) -> Claim | None:
    """The saved claim, or None if there is none or it's malformed (see read_claim_file)."""
    return read_claim_file(state_dir / CLAIM_FILE)
