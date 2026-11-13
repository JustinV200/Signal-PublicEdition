"""DuoWatch: spots Duo prompts in every tab as they appear, and tells the owner and the model.

It listens to each tab's frame events (navigations and detaches), so a prompt
is noticed the moment it loads, even between tool calls. On a new prompt (see
prompt_state for the once-per-prompt rule) it queues one notice for the next
tool result and posts one urgent voice note to the audiohub hub, marked to ring
through sleep and away. The note goes
through HeadsUpPings (pings.py): in the background, with timeouts, and a hub
that isn't running is logged and skipped, so no tool result fails. Its outcome
(spoken, dropped by a hub without ring-through, no hub, rate-limited) is kept
per tab: the notice ends with one line saying which, and wait_for_duo reads it.

Voice notes are also spaced at least min_heads_up_interval_s apart across all
tabs: a page could otherwise embed a Duo iframe over and over to have the owner
told "approve on your phone" every few seconds, priming them to approve an
attacker's push. The lockout and the model's notice are not rate-limited.

Each new prompt also starts a CodeRelay (code_relay), which reads Duo's
Verified Push code on [duo] code_relay_sites only and, once per prompt, queues
an updated notice with the code and posts one urgent code note. That note may
skip the global min_heads_up_interval_s, because the relay only starts after
the prompt's own heads-up was posted or rate-limited. Code relays are held to
the same interval per site instead, across tabs, voice note and notice alike,
so the known ways to put a real Duo prompt under an allowlisted site's name
(see duo/README.md) can't make "type it in Duo Mobile and approve" come often.
A capped relay's notice says a code was shown but not relayed.

Every main-frame navigation request is noted: one to Duo is vetted against the
tab's site (TabDuoState.vet_duo_navigation: its redirect chain, and the Referer
its first request carried), and a prompt that starts on a top-level Duo page
with no matching request (e.g. restored from the back/forward cache) loses its
site. So redirect chains through another host, navigations another page or
Claude started, and cache restores can't borrow the site's name.

is_in_duo is the live check behind the acting tools' lockout. It reads the
frames at call time instead of trusting the event bookkeeping.

At most one notice per tab waits for the model (the latest), so a page that
keeps re-adding a Duo iframe can't grow the queue or flood the next result.
"""

import logging
import time
import weakref
from collections.abc import Callable
from urllib.parse import urldefrag

from playwright.async_api import BrowserContext, Frame, Page, Request

from browser_tool.config import DuoSettings
from browser_tool.duo.code_relay import CodeRelay
from browser_tool.duo.failure_log import log_failure
from browser_tool.duo.hosts import is_duo_url
from browser_tool.duo.messages import (
    code_note,
    heads_up_note,
    model_notice,
    ping_line,
    shown_site,
)
from browser_tool.duo.pings import HeadsUpPings, PingOutcome, recent_gap_s
from browser_tool.duo.prompt_state import TabDuoState
from browser_tool.policy import host_of

logger = logging.getLogger(__name__)

# How long a notice waits for its prompt's heads-up delivery before saying
# "still sending"; a local hub answers in milliseconds.
NOTICE_PING_WAIT_S = 2.0
# wait_for_duo's wait: past the hub client's own timeouts (3 s connect, 5 s reply).
PING_WAIT_S = 8.5


class DuoWatch:
    """Watches a browser context's tabs for Duo prompts."""

    def __init__(
        self,
        settings: DuoSettings,
        clock: Callable[[], float] = time.monotonic,
        *,
        job_label: Callable[[], str | None] = lambda: None,
    ):
        """Set up the watcher; nothing is watched until watch() is called.

        Args:
            settings: The [duo] settings (voice switch, hub address, token file, timings,
                code relay sites).
            clock: Monotonic seconds; tests pass a fake.
            job_label: Returns the browser job's name (e.g. "docker job 1a2b3c"),
                which starts each voice note, or None for no prefix.

        Raises:
            ValueError: If a [duo] code_relay_sites pattern is malformed.
        """
        self._settings = settings
        self._clock = clock
        self._job_label = job_label
        self._pings = HeadsUpPings(settings)
        # When each allowlisted site last had a code relayed (voice note and notice).
        self._last_code_at: dict[str, float] = {}
        # Weak keys, so closed tabs don't pile up.
        self._tabs: weakref.WeakKeyDictionary[Page, TabDuoState] = weakref.WeakKeyDictionary()
        # Each tab's latest main-frame navigation request (its last redirect hop so far).
        self._navigations: weakref.WeakKeyDictionary[Page, Request] = weakref.WeakKeyDictionary()
        self._opened_by_duo: weakref.WeakSet[Page] = weakref.WeakSet()
        # Pending notices, the latest per tab; cleared by take_notices().
        self._notices: dict[Page, str] = {}
        self._code_relay = CodeRelay(settings, self._deliver_code)

    def is_in_duo(self, page: Page) -> bool:
        """The lockout check: is this tab showing (or possibly showing) a Duo prompt?

        Args:
            page: The tab to check.

        Returns:
            True while any frame is on a Duo host or one that can't be read, and for
            a popup a Duo tab opened, while that popup is on a page with no host
            (an about:blank or blob:null popup can be scripted by Duo itself).
        """
        if any(is_duo_url(frame.url) for frame in page.frames):
            return True
        return page in self._opened_by_duo and host_of(page.url) is None

    def watch(self, context: BrowserContext) -> None:
        """Follow every open and future tab of `context`. Call once per context, from the loop.

        Args:
            context: A freshly launched browser context.
        """
        for page in context.pages:
            self._watch_page(page)
        context.on("page", self._watch_page)

    async def take_notices(self) -> list[str]:
        """Return and clear the notices queued for the model: the latest one per tab.

        Each ends with its prompt's voice ping line (see messages.ping_line),
        waiting up to NOTICE_PING_WAIT_S for a delivery still in flight.
        """
        pending, self._notices = self._notices, {}
        interval_s = self._settings.min_heads_up_interval_s
        notices = []
        for page, notice in pending.items():
            outcome = await self._pings.outcome(page, NOTICE_PING_WAIT_S)
            notices.append(f"{notice}\n{ping_line(outcome, interval_s)}")
        return notices

    async def ping_outcome(self, page: Page, wait_s: float = PING_WAIT_S) -> PingOutcome | None:
        """The heads-up outcome of the tab's latest prompt (see HeadsUpPings.outcome).

        Args:
            page: The tab.
            wait_s: How long to wait for a delivery still in flight.
        """
        return await self._pings.outcome(page, wait_s)

    async def drain(self) -> None:
        """Wait for every code relay to finish, then every voice note to be delivered (tests)."""
        await self._code_relay.drain()
        await self._pings.drain()

    def _watch_page(self, page: Page) -> None:
        """Re-check `page` on frame changes, mark its popups from Duo, stop its relay on close."""

        def on_frame_change(_frame: Frame) -> None:
            self._safely(self._check, page)

        def on_popup(popup: Page) -> None:
            self._safely(self._note_popup, page, popup)

        def on_close(_page: Page) -> None:
            self._safely(self._code_relay.stop, page)

        def on_request(request: Request) -> None:
            self._safely(self._note_navigation, page, request)

        page.on("framenavigated", on_frame_change)
        page.on("framedetached", on_frame_change)
        page.on("popup", on_popup)
        page.on("close", on_close)
        page.on("request", on_request)
        self._safely(self._check, page)

    def _safely(self, handler: Callable[..., None], *args: object) -> None:
        """Run an event handler, which must never raise into Playwright's event dispatch."""
        try:
            handler(*args)
        except Exception as error:  # noqa: BLE001 - would break Playwright's event dispatch
            # The lockout doesn't depend on this: is_in_duo reads frames live.
            log_failure(logger, "Duo check", error)

    def _note_popup(self, opener: Page, popup: Page) -> None:
        """A popup opened by a tab in Duo counts as Duo while it is on a page with no host."""
        if self.is_in_duo(opener):
            self._opened_by_duo.add(popup)

    def _note_navigation(self, page: Page, request: Request) -> None:
        """Keep the tab's latest main-frame navigation request; vet one to Duo."""
        # is_navigation_request first: request.frame raises for service-worker requests.
        if not request.is_navigation_request() or request.frame != page.main_frame:
            return
        self._navigations[page] = request
        if is_duo_url(request.url):
            self._state_for(page).vet_duo_navigation(request)

    def _state_for(self, page: Page) -> TabDuoState:
        """The tab's Duo state, created on first use."""
        return self._tabs.setdefault(page, TabDuoState(self._settings.same_prompt_window_s))

    def _check(self, page: Page) -> None:
        """Update the tab's state, announce a new prompt, stop the code relay on leaving Duo."""
        state = self._state_for(page)
        frame_urls = [frame.url for frame in page.frames]
        now = self._clock()
        was_in_duo = state.is_in_duo
        if state.update(page.url, frame_urls, now):
            if is_duo_url(page.url) and not self._has_vetted_request(page):
                # No request to vet (a back/forward-cache restore, or one missed): fail closed.
                # Unreachable under Playwright (cache off), so covered by reasoning, not a test.
                state.site = None
            self._announce(page, state, now)
        elif was_in_duo and not state.is_in_duo:
            self._code_relay.stop(page)

    def _has_vetted_request(self, page: Page) -> bool:
        """True when the tab's latest main-frame navigation request is for the page it shows."""
        request = self._navigations.get(page)
        return request is not None and urldefrag(request.url).url == urldefrag(page.url).url

    def _announce(self, page: Page, state: TabDuoState, now: float) -> None:
        """Queue the model's notice, post the voice heads-up (rate-limited), look for a code."""
        tab_index = _tab_index(page)
        site = state.site
        logger.info("Duo prompt in tab %s for %s; acting tools paused", tab_index, shown_site(site))
        # Replaces any notice this tab still has pending: the latest is what's true now.
        self._notices[page] = model_notice(site, tab_index, site_names=self._settings.site_names)
        note = heads_up_note(site, self._job_label(), site_names=self._settings.site_names)
        self._pings.post_heads_up(page, note, now)
        # Started only now, after this prompt's heads-up was posted or rate-limited:
        # that is what lets its one code note skip the global interval (see _deliver_code).
        self._code_relay.start(page, state)

    def _deliver_code(self, page: Page, site: str, code: str) -> None:
        """Tell the model and the owner a prompt's code, at most once per site per interval.

        CodeRelay calls it once per prompt. The cap is min_heads_up_interval_s per
        site, across tabs; the global heads-up interval doesn't apply, because this
        prompt's heads-up already went out or was rate-limited.
        """
        tab_index = _tab_index(page)
        site_name = shown_site(site)
        now = self._clock()
        names = self._settings.site_names
        interval_s = self._settings.min_heads_up_interval_s
        gap_s = recent_gap_s(self._last_code_at.get(site), now, interval_s)
        if gap_s is not None:
            logger.info("Duo code for %s not relayed: the last was %.0f s ago", site_name, gap_s)
            notice = model_notice(site, tab_index, is_code_withheld=True, site_names=names)
            self._notices[page] = notice
            return
        self._last_code_at[site] = now
        # Never log the code itself.
        logger.info("Duo code found in tab %s for %s; relaying it", tab_index, site_name)
        self._notices[page] = model_notice(site, tab_index, code, site_names=names)
        self._pings.post_code(code_note(site, code, self._job_label(), site_names=names))


def _tab_index(page: Page) -> int | None:
    """The tab's index as tabs() lists it, or None once it's closed."""
    open_pages = page.context.pages
    return open_pages.index(page) if page in open_pages else None
