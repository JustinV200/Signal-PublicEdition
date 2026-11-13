"""Launch Edge for one visit, outside the tool runner, and say whether it's ok, busy or error.

Visit calls ctx.session.start() itself before the first target, so a launch failure
shows as busy or error rather than a generic navigation error. On the checker's own
profile, busy means another checker launch, the owner's plain-Edge sign-in window, or
the previous launch's msedge.exe still exiting, so a locked profile is retried for
up to PROFILE_LOCK_WAIT_S first.
"""

import asyncio
import logging
import time

from browser_tool.actions import ActionContext
from browser_tool.config import resolve_tool_path
from browser_tool.visit.result import STATUS_BUSY, STATUS_ERROR, STATUS_OK

logger = logging.getLogger(__name__)

# TODO: phase 0 checks whether the wait is needed at all, and whether this file
# tells a locked profile apart from other launch failures [unverified].
PROFILE_LOCKFILE = "lockfile"
PROFILE_LOCK_WAIT_S = 10.0
PROFILE_LOCK_POLL_S = 1.0


async def start_browser(ctx: ActionContext) -> str:
    """Start the session's Edge: STATUS_OK, STATUS_BUSY (profile locked) or STATUS_ERROR.

    Never raises for a launch failure; only the exception's type is logged, since
    Playwright's message text is never logged.
    """
    deadline = time.monotonic() + PROFILE_LOCK_WAIT_S
    while True:
        try:
            await ctx.session.start()
            return STATUS_OK
        except Exception as error:  # noqa: BLE001 - every launch failure is a status
            logger.warning("the browser didn't launch: %s", type(error).__name__)
        if not _is_profile_locked(ctx):
            return STATUS_ERROR
        if time.monotonic() >= deadline:
            logger.warning("the checker profile is still in use; giving up")
            return STATUS_BUSY
        await asyncio.sleep(PROFILE_LOCK_POLL_S)


def _is_profile_locked(ctx: ActionContext) -> bool:
    """True if the profile folder has Chromium's lock file (another Edge has it open)."""
    return (resolve_tool_path(ctx.settings.browser.profile_dir) / PROFILE_LOCKFILE).exists()
