"""The mail tool as the runner sees it: account statuses and one Gmail search.

MailClient is the interface gather.py pages through, so tests can fake it.
CliMailClient is the real one: it runs the mail tool's own CLI (`mail accounts`,
`mail search`) as a hidden child process, the same way digest_email runs
`mail send-self`, so this job never imports the mail tool's code.
"""

import json
import logging
import re
from typing import Protocol

from mail_digest.child_env import run_hidden_output
from mail_digest.settings import MAIL_CLI_TIMEOUT_S, MAIL_PROJECT

log = logging.getLogger(__name__)

OK_STATUS = "ok"
# The statuses `mail accounts` prints (tools/mail service/mailbox.py).
ACCOUNT_STATUSES = (OK_STATUS, "needs re-auth", "offline", "error")
# The start of one `mail accounts` row: alias, email (or "?"), status. What follows
# (a "  (detail)" note) is ignored, so odd detail text can't hide a status.
ACCOUNT_ROW = re.compile(
    r"(?P<alias>\S+)\s+\S+\s+(?P<status>" + "|".join(ACCOUNT_STATUSES) + r")(?=\s|$)"
)
# The message fields the model gets. The mail tool already wraps every email-derived
# string (from, to, subject, snippet) in <untrusted_email_content> tags.
MESSAGE_FIELDS = ("id", "thread_id", "date", "from", "to", "subject", "snippet", "labels")
# How the mail tool's CLI is started; a command is appended to it.
MAIL_COMMAND = ("uv", "run", "--project", str(MAIL_PROJECT), "--frozen", "--no-sync", "mail")


class MailToolError(Exception):
    """The mail tool's CLI failed, timed out or printed something unreadable."""


class MailClient(Protocol):
    """What gather.py needs from the mail tool."""

    def accounts(self) -> dict[str, str]:
        """Each saved alias's live status. Raises MailToolError."""
        ...

    def search(self, alias: str, query: str, max_results: int) -> list[dict]:
        """Message summaries matching a Gmail query, at most max_results. Raises MailToolError."""
        ...


class CliMailClient:
    """MailClient over the mail tool's CLI. command is how it's started (tests swap it)."""

    def __init__(self, command: tuple[str, ...] = MAIL_COMMAND) -> None:
        self._command = command

    def accounts(self) -> dict[str, str]:
        """Parse `mail accounts`. Rows that don't parse are logged and left out."""
        statuses = {}
        for line in self._run("mail accounts", ["accounts"]).splitlines():
            row = ACCOUNT_ROW.match(line.strip())
            if row:
                statuses[row["alias"]] = row["status"]
            elif line.strip():
                log.warning("unreadable `mail accounts` line: %r", line)
        return statuses

    def search(self, alias: str, query: str, max_results: int) -> list[dict]:
        """Parse `mail search` JSON, keeping MESSAGE_FIELDS of entries with a string id."""
        output = self._run("mail search", ["search", alias, query, "--max", str(max_results)])
        try:
            found = json.loads(output)
        except json.JSONDecodeError as error:
            raise MailToolError(f"mail search printed invalid JSON: {error}") from None
        if not isinstance(found, list):
            raise MailToolError("mail search didn't print a list")
        return [
            {field: item.get(field) for field in MESSAGE_FIELDS}
            for item in found
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]

    def _run(self, name: str, args: list[str]) -> str:
        """stdout of one mail CLI command. Raises MailToolError if it didn't exit 0 (logged)."""
        output = run_hidden_output(name, [*self._command, *args], MAIL_CLI_TIMEOUT_S)
        if output is None:
            raise MailToolError(f"{name} failed (see the log)")
        return output
