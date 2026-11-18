"""`mail check`: the setup window's health check. Local and read-only, no network, no sign-in.

It reads the saved account files and the OAuth client file. It can't tell that Google has
revoked or expired a sign-in (only a real call shows that, which `mail accounts` makes), so
a pass means "saved and readable", not "still accepted by Google".
"""

import argparse
import json
from pathlib import Path

from mail_tool.auth import TokenStore, load_client_config
from mail_tool.config import ACCOUNTS_DIR, CLIENT_SECRETS_PATH
from mail_tool.errors import AccountError, ReauthRequired, SetupError

EXIT_OK = 0
EXIT_FAILED = 1
# Prefix of every command a summary offers; it runs as shown from the repo root.
RUN_MAIL = "uv run --project tools/mail --frozen --no-sync mail"


def find_problem(store: TokenStore, client_path: Path) -> dict[str, str | None] | None:
    """The first thing wrong with the saved sign-ins, as a summary dict, or None when fine.

    Args:
        store: Where the accounts are saved.
        client_path: The OAuth client JSON (refreshing a sign-in needs it).
    """
    aliases = store.aliases()
    if not aliases:
        return {
            "words": "No Gmail account is signed in.",
            "fix": "Run setup mail, or `mail add <name> --email <address>`.",
            "command": None,  # needs the owner's address, so it can't run as shown
        }
    for alias in aliases:
        try:
            store.load(alias)
        except (ReauthRequired, AccountError):
            return {
                "words": f"The saved sign-in for {alias} is unreadable.",
                "fix": f"Sign {alias} in again.",
                "command": f"{RUN_MAIL} add {alias}",
            }
    try:
        load_client_config(client_path)
    except SetupError as error:
        return {
            "words": "The Google client file is missing or invalid.",
            "fix": str(error),
            "command": None,
        }
    return None


def check_accounts(args: argparse.Namespace) -> int:
    """`mail check`: print a one-line summary as JSON; exit 0 fine, 1 when sign-in needs fixing."""
    store = TokenStore(ACCOUNTS_DIR)
    problem = find_problem(store, CLIENT_SECRETS_PATH)
    if problem is not None:
        print(json.dumps(problem))
        return EXIT_FAILED
    count = len(store.aliases())
    words = f"{count} account{'s' if count != 1 else ''} saved (not tested against Google)"
    print(json.dumps({"words": words}))
    return EXIT_OK
