"""wait_until_off_duo: wait, read only, until a tab leaves Duo (or a login), closes or times out.

Shared by the wait_for_duo tool and visit mode's login wait. It never touches
the page: it only reads frame URLs, woken by the tab's framenavigated,
framedetached and close events, with a poll every POLL_S as a fallback for a
change no event reported. wait_for_settle then lets the landing finish its
redirects (wait_for_duo), also read only.
"""

import asyncio
import time
from collections.abc import Callable
from contextlib import suppress
from enum import Enum

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Frame, Page

# The fallback poll, for a change no frame event reported.
POLL_S = 1.0
# wait_for_settle: the main frame must stay put this long, within SETTLE_MAX_S.
SETTLE_QUIET_S = 1.0
SETTLE_MAX_S = 10.0


class WaitOutcome(Enum):
    """How a wait ended."""

    DONE = "done"  # the tab left Duo (and the login, for visit mode)
    TIMEOUT = "timeout"  # still waiting when timeout_s ran out
    CLOSED = "closed"  # the tab closed meanwhile


async def wait_until_off_duo(
    page: Page,
    timeout_s: float,
    is_waiting: Callable[[Page], bool],
    clock: Callable[[], float] = time.monotonic,
) -> WaitOutcome:
    """Wait until is_waiting(page) is False, the tab closes, or timeout_s passes.

    Args:
        page: The tab to watch. Nothing is clicked, typed or evaluated in it.
        timeout_s: How long to wait, in seconds.
        is_waiting: True while the tab still shows what is being waited out,
            e.g. DuoWatch.is_in_duo, or visit mode's "on the login host or Duo".
        clock: Monotonic seconds; tests may pass a fake.

    Returns:
        DONE, TIMEOUT or CLOSED.
    """
    changed = asyncio.Event()

    def on_change(_event: Frame | Page) -> None:
        changed.set()

    events = ("framenavigated", "framedetached", "close")
    for event in events:
        page.on(event, on_change)
    try:
        deadline = clock() + timeout_s
        while True:
            if page.is_closed():
                return WaitOutcome.CLOSED
            if not is_waiting(page):
                return WaitOutcome.DONE
            remaining_s = deadline - clock()
            if remaining_s <= 0:
                return WaitOutcome.TIMEOUT
            changed.clear()
            # A timeout here is just the fallback poll coming round.
            with suppress(TimeoutError):
                await asyncio.wait_for(changed.wait(), min(POLL_S, remaining_s))
    finally:
        for event in events:
            page.remove_listener(event, on_change)


async def wait_for_settle(
    page: Page, quiet_s: float = SETTLE_QUIET_S, max_s: float = SETTLE_MAX_S
) -> None:
    """Wait, read only, until the tab's main frame has loaded and not navigated for quiet_s.

    After Duo, a login hands off through pages that commit and redirect at once
    (e.g. a CAS page on the way back to the service); reading the landing
    before that ends would report the hand-off page. Gives up after max_s.

    Args:
        page: The tab. Nothing is clicked, typed or evaluated in it.
        quiet_s: How long the main frame must stay put.
        max_s: The most this waits in all.
    """
    navigated = asyncio.Event()

    def on_navigated(frame: Frame) -> None:
        if frame == page.main_frame:
            navigated.set()

    page.on("framenavigated", on_navigated)
    try:
        async with asyncio.timeout(max_s):
            with suppress(PlaywrightError):  # a closed tab: the caller reports it
                await page.wait_for_load_state("load")
            while not page.is_closed():
                navigated.clear()
                try:
                    await asyncio.wait_for(navigated.wait(), quiet_s)
                except TimeoutError:
                    return
    except TimeoutError:
        return  # still moving after max_s: report wherever it is now
    finally:
        page.remove_listener("framenavigated", on_navigated)
