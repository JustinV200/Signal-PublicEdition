"""Well-known filesystem locations for the mail tool.

Paths come from this file's place in the source tree
(tools/mail/src/mail_tool/config/paths.py), which holds because uv installs the
project in editable mode.
"""

from pathlib import Path

# parents: [0] config, [1] mail_tool, [2] src, [3] tools/mail
TOOL_ROOT: Path = Path(__file__).resolve().parents[3]

# tools/mail -> tools -> repo root
REPO_ROOT: Path = TOOL_ROOT.parents[1]

# Everything per-machine and secret lives here. Gitignored (tools/mail/.state/).
STATE_DIR: Path = TOOL_ROOT / ".state"

# The Desktop-app OAuth client the owner downloads from Google Cloud (see SETUP.md).
CLIENT_SECRETS_PATH: Path = STATE_DIR / "google_client.json"

# One DPAPI-encrypted <alias>.bin per signed-in account.
ACCOUNTS_DIR: Path = STATE_DIR / "accounts"

# Optional settings ([send] confirm = true). Kept in .state so one gitignore line covers it.
CONFIG_PATH: Path = STATE_DIR / "mail.toml"
