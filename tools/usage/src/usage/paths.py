"""Where the usage tool keeps its state: tools/usage/.state/ (gitignored).

Paths come from this file's place in the source tree
(tools/usage/src/usage/paths.py), which holds because uv installs the project
in editable mode.
"""

from pathlib import Path

# parents: [0] usage, [1] src, [2] tools/usage
TOOL_ROOT: Path = Path(__file__).resolve().parents[2]

STATE_DIR: Path = TOOL_ROOT / ".state"
# The one file the whiteboard reads: usage windows plus active subagents.
STATE_FILE: Path = STATE_DIR / "usage.json"
# Failures of the status line and hook, which can't print them anywhere useful.
ERROR_LOG: Path = STATE_DIR / "errors.log"
