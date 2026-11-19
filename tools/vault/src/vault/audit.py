"""Append-only JSONL audit log of fills, refusals and owner management actions.

Each line holds a UTC timestamp, the event, the credential id, origins (never
full URLs: query strings carry tokens) and the result code. Secrets never go
in. Same-user code can still rewrite the file; it's a record, not a boundary.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from vault.store import CREDENTIAL_ID_PATTERN

EVENT_FILL = "fill"
EVENT_INIT = "init"
EVENT_ADD = "add"
EVENT_REMOVE = "remove"
EVENT_POLICY = "policy"
# Logged in place of a requested id that isn't a valid id (it came from the model).
INVALID_ID_LABEL = "<invalid-id>"

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditEntry:
    """One audit line. Every field is non-secret by construction."""

    ts: str
    event: str
    credential_id: str
    result: str
    top_origin: str = ""
    frame_origin: str = ""
    # "auto" when the policy skipped the Allow/Deny dialog; "" (omitted) otherwise.
    confirm: str = ""


def safe_credential_id(credential_id: str) -> str:
    """Return `credential_id` if well-formed ("" for vault-level events), else a placeholder."""
    if credential_id == "":
        return ""
    if isinstance(credential_id, str) and CREDENTIAL_ID_PATTERN.match(credential_id):
        return credential_id
    return INVALID_ID_LABEL


def _non_empty(entry: AuditEntry) -> dict[str, str]:
    """The entry as a dict, leaving out `confirm` unless it is set (older lines stay the same)."""
    fields = asdict(entry)
    if not entry.confirm:
        del fields["confirm"]
    return fields


class AuditLog:
    """Appends `AuditEntry` lines to one JSONL file."""

    def __init__(self, path: Path) -> None:
        """Create a log that writes to `path` (the folder is created on first write)."""
        self._path = path

    def record(
        self,
        event: str,
        credential_id: str,
        result: str,
        *,
        top_origin: str = "",
        frame_origin: str = "",
        confirm: str = "",
    ) -> None:
        """Append one entry. A write failure is logged as a warning, not raised.

        A failed audit write must not turn a finished fill into an exception (the
        fill already happened), so it's reported on the logger instead.

        Args:
            event: One of the EVENT_* names.
            credential_id: The credential involved (sanitised here).
            result: The result code, e.g. a FillResult reason.
            top_origin: Origin label of the top-level page, for fills.
            frame_origin: Origin label of the login frame, for fills.
            confirm: "auto" if the dialog was skipped by policy.
        """
        entry = AuditEntry(
            ts=datetime.now(UTC).isoformat(timespec="seconds"),
            event=event,
            credential_id=safe_credential_id(credential_id),
            result=result,
            top_origin=top_origin,
            frame_origin=frame_origin,
            confirm=confirm,
        )
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(_non_empty(entry), sort_keys=True) + "\n")
        except OSError as error:
            _logger.warning("vault audit log write failed (%s)", type(error).__name__)
