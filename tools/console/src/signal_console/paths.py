"""Where the console keeps its state and where it finds the other Signal tools.

Every other module takes its paths from here (tests pass their own state folder).
Stdlib only, so the turn hook can import it cheaply.
"""

from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[2]  # tools/console
REPO_ROOT = TOOL_ROOT.parents[1]
STATE_DIR = TOOL_ROOT / ".state"
WEB_DIST_DIR = TOOL_ROOT / "web" / "dist"

LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 8790

# Files in STATE_DIR.
DAEMON_FILE = "daemon.json"  # {pid, createTime, port, startedAt} of the running server
LOCAL_KEY_FILE = "local-key"  # secret the turn hook and the CLI send as LOCAL_KEY_HEADER
CLAIM_FILE = "orchestrator.json"  # the claimed session's inbox {socket, token, label, claimedAt}
HUB_FILE = "hub.json"  # {pid, createTime} of the voice hub `console hub start` started
HUB_LOG_FILE = "hub.log"  # that hub's stdout and stderr
HUB_PREV_LOG_FILE = "hub.prev.log"  # the hub.log before the last start (why the last hub died)
HISTORY_FILE = "history.jsonl"  # recent message/voice events, replayed on connect
SERVER_LOG_FILE = "server.log"  # output of a server `console open` started
HOOK_LOG_FILE = "hook.log"  # turn hook failures (the hook must never print)
TASKS_FILE = "tasks.json"  # the orchestrator's task list (packages/tasks), via `console tasks`
SESSION_MODELS_FILE = "session-models.json"  # {session_id: {model, at}}, from the session hook
SETTINGS_BACKUP_FILE = "settings.local.bak.json"  # settings.local.json before its last write
MODELS_LOCK_FILE = "models.lock"  # one model or effort pick written at a time

LOCAL_KEY_HEADER = "X-Console-Key"

# Signal's local Claude Code settings: the console writes only `model` and `effortLevel` there.
LOCAL_SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.local.json"

# The voice hub (tools/audiohub). Its port is audiohub's default [ipc] port.
AUDIOHUB_ROOT = REPO_ROOT / "tools" / "audiohub"
HUB_TOKEN_PATH = AUDIOHUB_ROOT / ".cache" / "ipc-token"
# The hub's own {pid, create_time} record, written by every `audiohub run`; Stop falls back to it.
HUB_SELF_RECORD_PATH = AUDIOHUB_ROOT / ".cache" / "hub.json"
# Voice's model and effort pick (signal_modelchoice); the brain reads it before each turn.
BRAIN_CHOICE_PATH = AUDIOHUB_ROOT / ".cache" / "brain-choice.json"
# shortcut: assumes audiohub.toml keeps the default port; read its [ipc] port if that changes.
HUB_PORT = 8765

# tools/usage keeps each session's running subagents here (format in its README).
USAGE_FILE_PATH = REPO_ROOT / "tools" / "usage" / ".state" / "usage.json"

# The whiteboard daemon writes its port and API token here.
WHITEBOARD_STATE_DIR = REPO_ROOT / "tools" / "whiteboard" / ".state"

# tools/browser's dedicated Edge profile: an msedge.exe using it is the desktop browser.
BROWSER_PROFILE_DIR = REPO_ROOT / "tools" / "browser" / ".profile"
