"""The JSON shapes the daemon returns for a session: a one-line summary and the full status.

Kept apart from ManagedSession so the wire format can change without touching
session logic. Costs are rounded for reading; times are local date-times.
"""

from typing import Any

from claude_sessions.daemon.session.managed import ManagedSession
from claude_sessions.text import format_local_time

COST_DECIMALS = 4


def session_summary(session: ManagedSession) -> dict[str, Any]:
    """The fields list() shows for each session.

    Args:
        session: Any managed session.

    Returns:
        id, repo, state, liveness, Claude session id, cost and last update.
    """
    record = session.record
    return {
        "id": record.id,
        "repo": record.repo_name,
        "repo_path": record.repo_path,
        "state": record.state.value,
        "is_live": session.is_live,
        "claude_session_id": record.claude_session_id,
        "cost_usd": round(record.cost_usd, COST_DECIMALS),
        "updated_at": format_local_time(record.updated_at),
    }


def session_status(session: ManagedSession, last_n: int) -> dict[str, Any]:
    """Everything status() shows: the summary plus model, mode, approval, error and texts.

    Args:
        session: Any managed session.
        last_n: How many of the newest assistant texts to include (0 for none).

    Returns:
        The status, with last_texts oldest first.
    """
    record = session.record
    return {
        **session_summary(session),
        "model": record.model,
        "permission_mode": record.permission_mode,
        "pending_approval": session.pending_approval,
        "error": record.error,
        "created_at": format_local_time(record.created_at),
        "last_texts": record.last_texts[-last_n:] if last_n > 0 else [],
    }
