"""Well-known filesystem locations for sleepmode, and the whiteboard files it reads.

Paths come from this file's place in the source tree
(tools/sleepmode/src/sleepmode/config/paths.py), which holds because uv installs the
project in editable mode.
"""

from pathlib import Path

# parents: [0] config, [1] sleepmode, [2] src, [3] tools/sleepmode
TOOL_ROOT: Path = Path(__file__).resolve().parents[3]

# tools/sleepmode -> tools -> repo root
REPO_ROOT: Path = TOOL_ROOT.parents[1]

# Runtime state: state.json, the log, the wake task's XML while registering. Gitignored.
STATE_DIR: Path = TOOL_ROOT / ".state"
STATE_FILE: Path = STATE_DIR / "state.json"
LOG_FILE: Path = STATE_DIR / "sleepmode.log"

# The optional per-machine config ([lighting]). Gitignored; sleepmode.example.toml is the template.
CONFIG_FILE: Path = TOOL_ROOT / "sleepmode.toml"

# The whiteboard's uv project (sleep starts its daemon), its daemon's discovery files
# (daemon.json, token) and its optional config.
WHITEBOARD_ROOT: Path = REPO_ROOT / "tools" / "whiteboard"
WHITEBOARD_STATE_DIR: Path = WHITEBOARD_ROOT / ".state"
WHITEBOARD_CONFIG: Path = WHITEBOARD_ROOT / "whiteboard.toml"
