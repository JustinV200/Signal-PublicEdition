"""Read the claimed session's running subagents from tools/usage's usage.json.

The usage hooks (SubagentStart/SubagentStop) keep `sessions[<id>].agents` in
that file. Its README's reader rules apply: read it whole and quickly, at
about 1 Hz, and on a PermissionError (a writer is replacing it) or bad JSON
keep the last good copy. The file is re-read only when its mtime changes.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Matches tools/usage's STALE_AGENT_HOURS: an agent not seen for this long was killed silently.
AGENT_FRESH_S = 2 * 60 * 60.0

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionAgents:
    """What usage.json says about one session.

    Attributes:
        count: Its subagents seen in the last AGENT_FRESH_S, or None if usage.json is unreadable.
        updated_at: Epoch seconds of its last usage hook, or None if it has none.
    """

    count: int | None
    updated_at: float | None


class UsageAgents:
    """Keeps the last good copy of usage.json and answers per-session agent counts."""

    def __init__(self, path: Path) -> None:
        """Set up; the file is read on the first `read`."""
        self._path = path
        self._mtime_ns: int | None = None
        self._sessions: dict[str, Any] | None = None

    def read(self, session_id: str | None, now: float) -> SessionAgents:
        """The session's running agents and last usage activity.

        Args:
            session_id: The claimed session's id, or None if no turn hook has said it yet.
            now: Epoch seconds, for the freshness cut.
        """
        self._refresh()
        if self._sessions is None:
            return SessionAgents(None, None)
        session = self._sessions.get(session_id) if session_id else None
        if not isinstance(session, dict):
            return SessionAgents(0, None)  # usage drops a session once its last agent stops
        agents = session.get("agents")
        agents = agents if isinstance(agents, list) else []
        seen = [_epoch(agent.get("seen_at")) for agent in agents if isinstance(agent, dict)]
        count = sum(1 for at in seen if at is not None and now - at < AGENT_FRESH_S)
        return SessionAgents(count, _epoch(session.get("updated_at")))

    def _refresh(self) -> None:
        try:
            mtime_ns = self._path.stat().st_mtime_ns
            if mtime_ns == self._mtime_ns:
                return
            payload = json.loads(self._path.read_bytes())
        except FileNotFoundError:
            self._mtime_ns, self._sessions = None, None  # usage isn't set up (or not yet)
            return
        # RecursionError: JSON nested too deep for the parser.
        except (OSError, ValueError, RecursionError) as error:
            log.debug("keeping the last usage.json: %s", error)  # retried next tick
            return
        sessions = payload.get("sessions") if isinstance(payload, dict) else None
        self._mtime_ns = mtime_ns
        self._sessions = sessions if isinstance(sessions, dict) else {}


def _epoch(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None
