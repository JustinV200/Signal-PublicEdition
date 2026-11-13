"""The last announced level per agent, in .state/levels.json (gitignored).

Shape: {"<session id>:<agent id or main>": <level>}. Entries are tiny, and the
oldest are dropped past MAX_ENTRIES so the file can't grow forever.
"""

import json
import os
from pathlib import Path

# parents: [0] contextmeter, [1] src, [2] tools/contextmeter
TOOL_ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = TOOL_ROOT / ".state" / "levels.json"
ERROR_LOG = TOOL_ROOT / ".state" / "errors.log"

MAX_ENTRIES = 500


def agent_key(session_id: str, agent_id: str | None) -> str:
    """Return the state key for one agent of one session."""
    return f"{session_id}:{agent_id or 'main'}"


def load_levels(state_file: Path) -> dict[str, int]:
    """Return the saved levels, or {} if the file is missing or unreadable."""
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_level(state_file: Path, key: str, level: int) -> None:
    """Set `key` to `level` and write the file atomically.

    TODO: no lock, so two parallel tool calls of one agent can race and one
    write is lost (worst case a line is repeated once); add a lock if that bites.

    Raises:
        OSError: The file can't be written.
    """
    levels = load_levels(state_file)
    levels.pop(key, None)  # re-insert so the newest key is last
    levels[key] = level
    while len(levels) > MAX_ENTRIES:
        levels.pop(next(iter(levels)))
    state_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = state_file.with_name(f"{state_file.name}.{os.getpid()}.tmp")
    temp_file.write_text(json.dumps(levels), encoding="utf-8")
    os.replace(temp_file, state_file)
