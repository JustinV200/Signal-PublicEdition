"""`CliContext`: the files, prompts and streams a CLI command uses, injectable for tests."""

import getpass
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from vault.audit import AuditLog
from vault.paths import default_audit_path, default_store_path
from vault.unlock import Unlocker, unlocker_for


@dataclass(frozen=True)
class CliContext:
    """Collaborators of the CLI commands.

    Attributes:
        store_path: The vault's store.json.
        audit: The audit log.
        unlocker_for: Returns the unlocker for a provider name.
        stdin: Checked with isatty() before any management command.
        read_secret: No-echo prompt (getpass).
        ask_line: Echoing prompt for confirmations (input).
        out: Writes one line of normal output.
    """

    store_path: Path
    audit: AuditLog
    unlocker_for: Callable[[str], Unlocker]
    stdin: TextIO
    read_secret: Callable[[str], str]
    ask_line: Callable[[str], str]
    out: Callable[[str], None]


def default_context() -> CliContext:
    """Return the context for a real run: default paths, real unlockers, the real terminal."""
    return CliContext(
        store_path=default_store_path(),
        audit=AuditLog(default_audit_path()),
        unlocker_for=unlocker_for,
        stdin=sys.stdin,
        read_secret=getpass.getpass,
        ask_line=input,
        out=print,
    )
