"""HeadsUpPings: the owner's voice notes for Duo prompts, rate-limited, outcomes kept per tab.

Notes go to the audiohub hub through signal_hub_notify.Notifier, in the
background, so nothing waits on the hub. The heads-up for a tab's latest prompt
is remembered (its delivery task, or why none was sent), so the model's notice
and wait_for_duo can say whether the owner heard it: spoken, dropped (only by
a hub that doesn't honour ring_through), no hub, or skipped by the rate limit.
Duo notes ring through sleep and away (messages._duo_note), so a current hub
speaks them; the owner may still not answer, which wait_for_duo plans for.

Heads-ups are spaced at least min_heads_up_interval_s apart across all tabs (see
duo/README.md for why). Code notes skip that interval; DuoWatch caps them per
site instead, with recent_gap_s.
"""

import asyncio
import logging
import weakref
from enum import Enum

from playwright.async_api import Page
from signal_hub_notify import Delivery, HubNote, Notifier

from browser_tool.config import DuoSettings, resolve_tool_path

logger = logging.getLogger(__name__)


class PingSkip(Enum):
    """Why a prompt has no delivery to report."""

    RATE_LIMITED = "rate_limited"  # a heads-up went out under min_heads_up_interval_s ago
    VOICE_OFF = "voice_off"  # [duo] voice_heads_up is off
    STILL_SENDING = "still_sending"  # the delivery hadn't finished when asked


PingOutcome = Delivery | PingSkip


class HeadsUpPings:
    """Posts voice notes for Duo prompts and keeps each tab's latest heads-up outcome."""

    def __init__(self, settings: DuoSettings):
        """Set up the notifier (only when voice_heads_up is on); nothing is sent yet.

        Args:
            settings: The [duo] settings (voice switch, hub address, token file,
                min_heads_up_interval_s).
        """
        self._interval_s = settings.min_heads_up_interval_s
        self._notifier: Notifier | None = None
        if settings.voice_heads_up:
            token_file = resolve_tool_path(settings.hub_token_file)
            self._notifier = Notifier(settings.hub_host, settings.hub_port, token_file)
        self._last_heads_up_at: float | None = None
        # Weak keys, so closed tabs don't pile up.
        self._by_tab: weakref.WeakKeyDictionary[Page, asyncio.Task[Delivery] | PingSkip] = (
            weakref.WeakKeyDictionary()
        )

    def post_heads_up(self, page: Page, note: HubNote, now: float) -> None:
        """Post a new prompt's heads-up, at most one per min_heads_up_interval_s.

        Args:
            page: The tab the prompt is in; its outcome replaces any earlier one.
            note: The heads-up note.
            now: The current monotonic time in seconds.
        """
        if self._notifier is None:
            self._by_tab[page] = PingSkip.VOICE_OFF
            return
        gap_s = recent_gap_s(self._last_heads_up_at, now, self._interval_s)
        if gap_s is not None:
            logger.info("Duo heads-up skipped: the last one was %.0f s ago", gap_s)
            self._by_tab[page] = PingSkip.RATE_LIMITED
            return
        self._last_heads_up_at = now
        self._by_tab[page] = self._notifier.post(note)

    def post_code(self, note: HubNote) -> None:
        """Post a code note (the caller has applied its per-site cap); no-op with voice off."""
        if self._notifier is not None:
            self._notifier.post(note)

    async def outcome(self, page: Page, wait_s: float) -> PingOutcome | None:
        """The tab's latest heads-up outcome, waiting up to wait_s for a delivery to finish.

        Args:
            page: The tab.
            wait_s: How long to wait for a delivery still in flight. Deliveries
                end on their own within the hub client's timeouts (about 8 s).

        Returns:
            The Delivery, a PingSkip (STILL_SENDING if wait_s ran out), or None
            when the tab never had a prompt announced.
        """
        record = self._by_tab.get(page)
        if not isinstance(record, asyncio.Task):
            return record
        # asyncio.wait never cancels the delivery, unlike wait_for.
        done, _ = await asyncio.wait({record}, timeout=wait_s)
        return record.result() if done else PingSkip.STILL_SENDING

    async def drain(self) -> None:
        """Wait for every posted note to be delivered (tests)."""
        if self._notifier is not None:
            await self._notifier.drain()


def recent_gap_s(last: float | None, now: float, interval_s: float) -> float | None:
    """Seconds since `last` if under interval_s, else None (also for no `last`).

    Args:
        last: When the last note of this kind went out (monotonic s), or None.
        now: The current monotonic time in seconds.
        interval_s: The minimum spacing.
    """
    if last is None or now - last >= interval_s:
        return None
    return now - last
