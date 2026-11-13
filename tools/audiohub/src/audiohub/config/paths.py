"""Well-known filesystem locations for audiohub.

Paths are derived from this file's location inside the source tree
(tools/audiohub/src/audiohub/config/paths.py). That holds because uv installs
the project in editable mode; a non-editable install into site-packages would
break these paths.
"""

from pathlib import Path

# parents: [0] config, [1] audiohub, [2] src, [3] tools/audiohub
TOOL_ROOT: Path = Path(__file__).resolve().parents[3]

# tools/audiohub -> tools -> repo root
REPO_ROOT: Path = TOOL_ROOT.parents[1]

# Downloaded model files (TTS, etc.). Gitignored.
MODELS_DIR: Path = TOOL_ROOT / "models"

# Small runtime state files that must survive a crash (e.g. ducked volumes). Gitignored.
CACHE_DIR: Path = TOOL_ROOT / ".cache"

# Voice's model and effort pick, written by the console (format: signal_modelchoice).
BRAIN_CHOICE_PATH: Path = CACHE_DIR / "brain-choice.json"

# Optional per-machine config. Gitignored; see audiohub.example.toml.
DEFAULT_CONFIG_PATH: Path = TOOL_ROOT / "audiohub.toml"

# The claimed orchestrator's inbox, written by `console claim` (tools/console,
# owner-only). The voice hand-off reads it to reach the main Signal session.
ORCHESTRATOR_CLAIM_PATH: Path = REPO_ROOT / "tools" / "console" / ".state" / "orchestrator.json"

# Other tools' state, read (never imported) to drop notifications while the owner
# is asleep (sleepmode) or away (the brief tool's away mode). See kernel/ipc/presence.py.
SLEEPMODE_STATE_PATH: Path = REPO_ROOT / "tools" / "sleepmode" / ".state" / "state.json"
BRIEF_AWAY_PATH: Path = REPO_ROOT / "tools" / "brief" / ".state" / "away.json"
