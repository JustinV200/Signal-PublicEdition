"""Well-known filesystem locations and fixed values for the calendar tool.

Paths come from this file's place in the source tree
(tools/calendar/src/calendar_tool/paths.py), which holds because uv installs
the project in editable mode.
"""

from pathlib import Path

# parents: [0] calendar_tool, [1] src, [2] tools/calendar
TOOL_ROOT: Path = Path(__file__).resolve().parents[2]

# tools/calendar -> tools -> repo root
REPO_ROOT: Path = TOOL_ROOT.parents[1]

# Per-machine and secret state. Gitignored (tools/calendar/.state/).
STATE_DIR: Path = TOOL_ROOT / ".state"

# The DPAPI-encrypted {"email", "refresh_token"} of the one signed-in account.
TOKEN_PATH: Path = STATE_DIR / "token.bin"

# The idle board's agenda, rewritten by `calendar sync-cache`.
CACHE_PATH: Path = STATE_DIR / "agenda.json"

# The last sync-cache outcome (cli/sync_status.py), since the scheduled run has no stderr.
SYNC_STATUS_PATH: Path = STATE_DIR / "sync_status.json"

# The Desktop-app OAuth client is the mail tool's (same Google Cloud project).
CLIENT_SECRETS_PATH: Path = REPO_ROOT / "tools" / "mail" / ".state" / "google_client.json"

# The account whose calendars the board shows (`calendar add` checks the sign-in matches).
OWNER_EMAIL = "owner@example.com"
