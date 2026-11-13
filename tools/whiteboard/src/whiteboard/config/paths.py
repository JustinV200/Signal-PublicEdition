"""Well-known filesystem locations for the whiteboard tool.

Paths are derived from this file's location inside the source tree
(tools/whiteboard/src/whiteboard/config/paths.py). That holds because uv installs
the project in editable mode; a non-editable install into site-packages would
break these paths.
"""

from pathlib import Path

# parents: [0] config, [1] whiteboard, [2] src, [3] tools/whiteboard
TOOL_ROOT: Path = Path(__file__).resolve().parents[3]

# tools/whiteboard -> tools -> repo root
REPO_ROOT: Path = TOOL_ROOT.parents[1]

# Runtime state: scene.json, calibration.json, snapshots/, the Edge profile, logs. Gitignored.
STATE_DIR: Path = TOOL_ROOT / ".state"

# The owner's knowledge base. The TODO view reads its week plans (and may tick a box).
LIFE_DIR: Path = REPO_ROOT / "life"

# The console's task list (written by `console tasks`) and tools/usage's usage file:
# board_tasks_show draws the task grid from them (read-only).
CONSOLE_TASKS_FILE: Path = REPO_ROOT / "tools" / "console" / ".state" / "tasks.json"
USAGE_FILE: Path = REPO_ROOT / "tools" / "usage" / ".state" / "usage.json"

# tools/calendar's cached agenda (Google Calendar events); the idle view reads it, read-only.
AGENDA_FILE: Path = REPO_ROOT / "tools" / "calendar" / ".state" / "agenda.json"

# tools/sleepmode's state; a daemon started while it says asleep opens on the night view.
SLEEPMODE_STATE_FILE: Path = REPO_ROOT / "tools" / "sleepmode" / ".state" / "state.json"

# Optional per-machine config. Gitignored; see whiteboard.example.toml.
DEFAULT_CONFIG_PATH: Path = TOOL_ROOT / "whiteboard.toml"
