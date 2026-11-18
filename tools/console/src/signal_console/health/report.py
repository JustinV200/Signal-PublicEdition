"""Run every console check in display order: the list `console doctor` prints and /api/health sends.

Every check is a local read (files, the process table, the pipe listing), so
the list is the same with the server up or down. A check that breaks
unexpectedly becomes an attention row naming the error, so one bad file never
hides the other rows.
"""

import logging
from collections.abc import Callable
from datetime import datetime

from signal_console.health.claim_check import claim_row
from signal_console.health.hook_activity import hook_errors_row, last_report_row
from signal_console.health.hook_settings import hook_rows
from signal_console.health.inputs import HealthPaths
from signal_console.health.local_checks import edge_row, hub_log_row, web_build_row, whiteboard_row
from signal_console.health.row import ATTENTION, HealthRow
from signal_console.health.server_check import server_rows

log = logging.getLogger(__name__)


def health_rows(paths: HealthPaths, now: datetime | None = None) -> list[HealthRow]:
    """Check everything and return one row per check.

    Args:
        paths: Where to look (HealthPaths() for this checkout; tests pass temp folders).
        now: The current time, timezone-aware; defaults to now.

    Returns:
        The rows: server, port, page, claim, turn hook, session hook, hooks
        firing twice, last hook report, hook errors, Edge, whiteboard, hub log.
    """
    now = now or datetime.now().astimezone()
    checks: list[tuple[str, Callable[[], list[HealthRow]]]] = [
        ("server", lambda: server_rows(paths)),
        ("web-build", lambda: [web_build_row(paths)]),
        ("claim", lambda: [claim_row(paths, now)]),
        ("hooks", lambda: hook_rows(paths)),
        ("hook-report", lambda: [last_report_row(paths)]),
        ("hook-errors", lambda: [hook_errors_row(paths, now)]),
        ("edge", lambda: [edge_row(paths)]),
        ("whiteboard", lambda: [whiteboard_row(paths)]),
        ("hub-log", lambda: [hub_log_row(paths)]),
    ]
    rows: list[HealthRow] = []
    for check_id, check in checks:
        rows += _guarded(check_id, check)
    return rows


def _guarded(check_id: str, check: Callable[[], list[HealthRow]]) -> list[HealthRow]:
    try:
        return check()
    except Exception as error:  # noqa: BLE001 - one broken check must not hide the rest
        log.warning("health check %s failed: %r", check_id, error)
        words = f"This check couldn't run ({type(error).__name__})."
        fix = "Run console doctor in a terminal: the warning line it prints names the cause."
        return [HealthRow(check_id, check_id, ATTENTION, "unchecked", words, fix)]
