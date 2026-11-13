"""SessionRecord: everything the daemon remembers about one managed session, and its JSON form.

Records outlive the daemon (see store.py), so a session can be found and
resumed after a restart by its managed id or its Claude session id.
"""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from claude_sessions.ipc import MAX_STATUS_TEXTS

# A long final report is kept whole up to this size; status is for reading
# what Claude said, and the full transcript stays in ~/.claude/projects.
MAX_TEXT_CHARS = 8000
TRUNCATED_MARK = "\n[… truncated]"


class SessionState(StrEnum):
    """Where a managed session is in its life."""

    IDLE = "idle"  # Live, waiting for the next prompt.
    WORKING = "working"  # Live, starting up or running a turn.
    AWAITING_PERMISSION = "awaiting_permission"  # Live, a tool call waits for the owner.
    STOPPED = "stopped"  # No CLI process; can be resumed.
    ERROR = "error"  # The last turn failed, or the CLI died (then not live).


@dataclass
class SessionRecord:
    """One managed session's metadata. Mutable: the session updates it as it runs.

    Attributes:
        id: The daemon's id for the session, e.g. "s-1a2b3c4d".
        repo_name: The repo folder's name, e.g. "OtherRepo".
        repo_path: Absolute path the session runs in.
        claude_session_id: The Claude Code session UUID (transcript name; used to resume).
        model: The requested model, or None for the settings' default.
        permission_mode: "default", "acceptEdits" or "plan".
        state: Current state.
        created_at: Creation time, seconds since the epoch.
        updated_at: Last change, seconds since the epoch.
        cost_usd: Total cost reported by the CLI across this record's runs.
        last_texts: The newest assistant texts, oldest first, at most MAX_STATUS_TEXTS.
        error: The last failure, when state is ERROR.
    """

    id: str
    repo_name: str
    repo_path: str
    claude_session_id: str
    model: str | None
    permission_mode: str
    state: SessionState
    created_at: float
    updated_at: float
    cost_usd: float = 0.0
    last_texts: list[str] = field(default_factory=list)
    error: str | None = None

    def add_text(self, text: str) -> None:
        """Keep one assistant text, capped in size, dropping the oldest beyond MAX_STATUS_TEXTS.

        Args:
            text: The text block Claude wrote.
        """
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS] + TRUNCATED_MARK
        self.last_texts.append(text)
        del self.last_texts[:-MAX_STATUS_TEXTS]

    def to_json(self) -> dict[str, Any]:
        """The record as JSON-ready data."""
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_json(cls, data: Any) -> "SessionRecord":
        """Rebuild a record from to_json() output read back from disk.

        Args:
            data: One decoded JSON object.

        Returns:
            The record.

        Raises:
            ValueError: A field is missing or has the wrong type.
        """
        if not isinstance(data, dict):
            raise ValueError("a session record must be a JSON object")
        try:
            record = cls(**{**data, "state": SessionState(data["state"])})
        except (KeyError, TypeError) as error:
            raise ValueError(f"malformed session record: {error}") from error
        _check_types(record)
        return record


def _check_types(record: SessionRecord) -> None:
    """Reject records whose fields were hand-edited into the wrong types."""
    text_fields = (record.id, record.repo_name, record.repo_path, record.claude_session_id)
    if not all(isinstance(value, str) and value for value in text_fields):
        raise ValueError(f"session record {record.id!r} has a blank or non-text id/repo field")
    numbers = (record.created_at, record.updated_at, record.cost_usd)
    if not all(isinstance(value, int | float) for value in numbers):
        raise ValueError(f"session record {record.id!r} has a non-numeric time or cost")
    if not isinstance(record.last_texts, list) or not all(
        isinstance(text, str) for text in record.last_texts
    ):
        raise ValueError(f"session record {record.id!r} has malformed last_texts")
