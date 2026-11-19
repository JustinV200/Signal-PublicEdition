"""refresh_cache: `sync-cache` after a write, so the idle board shows the change straight away.

Unlike the `sync-cache` command it never raises: the write already happened, and
a failed refresh only leaves the board stale until the scheduled sync. The
outcome still goes to the sync status file, and a failure is logged.
"""

import logging
from datetime import datetime
from pathlib import Path

from calendar_tool.agenda.cache import sync_cache
from calendar_tool.agenda.sync_status import record_sync_status
from calendar_tool.errors import CalendarError
from calendar_tool.google_api import CalendarClient

logger = logging.getLogger(__name__)


def refresh_cache(
    client: CalendarClient, cache_path: Path, status_path: Path, now: datetime
) -> bool:
    """Rewrite the agenda cache and record the outcome.

    Args:
        client: The API client the write used.
        cache_path: Usually paths.CACHE_PATH.
        status_path: Usually paths.SYNC_STATUS_PATH.
        now: Timezone-aware; the "updated" stamp.

    Returns:
        True when the cache was rewritten, False when the refresh failed (logged).
    """
    try:
        _, skipped = sync_cache(client, cache_path, now)
    except CalendarError as error:
        record_sync_status(status_path, now, error)
        logger.warning("agenda cache not refreshed after a change: %s", error)
        return False
    record_sync_status(status_path, now, skipped=skipped)
    return True
