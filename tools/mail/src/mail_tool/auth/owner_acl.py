"""restrict_to_owner: make a file only the current Windows user can open, before a secret goes in.

Same icacls sequence as tools/sessions (tokens/token_file.py), copied because
the tools are separate uv projects. DPAPI is the main protection for the token
files; the ACL keeps other local users from even reading the ciphertext.
"""

import getpass
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

OWNER_ONLY_MODE = 0o600


def restrict_to_owner(path: Path) -> None:
    """Limit an existing file to the current user; log (don't fail) if that isn't possible.

    Inheritance is removed, so the ACL stays with the file when it is renamed.

    Args:
        path: The file.
    """
    if os.name != "nt":
        path.chmod(OWNER_ONLY_MODE)
        return
    user = getpass.getuser()
    domain = os.environ.get("USERDOMAIN")
    account = f"{domain}\\{user}" if domain else user
    # Drop inherited entries and grant full control to this user alone.
    command = ["icacls", str(path), "/inheritance:r", "/grant:r", f"{account}:F"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        logger.warning(
            "Couldn't restrict %s to %s (icacls: %s); other local users may read the file",
            path,
            account,
            (completed.stdout + completed.stderr).strip(),
        )
