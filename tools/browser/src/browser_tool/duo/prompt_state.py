"""Once-per-prompt bookkeeping for one tab's Duo prompts. Pure: no Playwright, no clock.

The rule:
- A tab is in a Duo prompt while any of its frames (main frame or iframe) is on
  a Duo host. Redirect hops from one Duo page to another never leave Duo, so a
  whole redirect chain is one prompt.
- Entering Duo starts a new prompt, unless the tab left Duo less than
  `same_prompt_window_s` ago: then it's the same prompt bouncing out and back
  in (e.g. Duo -> the site's login page -> Duo), and nothing new is announced.
- The prompt's site is the tab's last non-Duo top-level host, so a top-level
  redirect to Duo still names the site the owner was logging in to. A
  top-level page with no host (about:blank, blob:, data:) clears it: such a
  page can be put in a tab by another site (an opener can set its location),
  so it must never borrow the name of the site the tab showed before.
- "Last non-Duo top-level host" alone isn't enough. Redirect hops never commit,
  so site -> evil.example -> 302 -> the attacker's Duo would read as the site.
  And a tab showing the site can be sent straight to Duo by something else: the
  page that opened it, a popup it opened, a third-party frame setting
  top.location, or Claude's own navigate. So each top-level navigation request
  to Duo is vetted (vet_duo_navigation): every hop of its redirect chain must be
  on Duo or on the site, and the chain's first request must carry a Referer on
  the site. A Referer on Duo counts only while the tab's top-level page is
  already on Duo (a hop inside a prompt vetted on the way in). Anything else, a
  missing Referer included, forgets the site.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from browser_tool.duo.hosts import is_duo_host, is_duo_url
from browser_tool.policy import host_of


class NavigationHop(Protocol):
    """The part of a navigation request this module reads (Playwright's Request fits)."""

    @property
    def url(self) -> str:
        """The hop's URL."""
        ...

    @property
    def redirected_from(self) -> "NavigationHop | None":
        """The hop that redirected to this one, or None for the chain's first."""
        ...

    @property
    def headers(self) -> dict[str, str]:
        """The hop's request headers, names lower-cased.

        Playwright's sync view, which carries the Referer on Edge. Reading it
        there keeps vetting synchronous, so it's done before the page commits
        and the prompt is announced.
        """
        ...


@dataclass
class TabDuoState:
    """What one tab last showed, for deciding when a new Duo prompt starts.

    Attributes:
        same_prompt_window_s: How soon a return to Duo still counts as the same prompt.
        is_in_duo: Whether the tab showed a Duo frame at the last update.
        is_top_level_duo: Whether the tab's top-level page was on Duo then.
        site: The tab's last non-Duo top-level host, or None if it never had one or
            the last non-Duo top-level page had no host.
        left_duo_at: When the tab last left Duo (monotonic seconds), or None.
    """

    same_prompt_window_s: float
    is_in_duo: bool = False
    is_top_level_duo: bool = False
    site: str | None = None
    left_duo_at: float | None = None

    def update(self, main_url: str, frame_urls: Iterable[str], now: float) -> bool:
        """Record what the tab shows now.

        Args:
            main_url: The tab's top-level URL.
            frame_urls: The URL of every frame in the tab, the main frame's included.
            now: The current monotonic time in seconds.

        Returns:
            True only when this update starts a new Duo prompt.
        """
        self.is_top_level_duo = is_duo_url(main_url)
        if not self.is_top_level_duo:
            self.site = host_of(main_url)
        was_in_duo = self.is_in_duo
        self.is_in_duo = any(is_duo_url(url) for url in frame_urls)
        if was_in_duo and not self.is_in_duo:
            self.left_duo_at = now
        if was_in_duo or not self.is_in_duo:
            return False
        return not self._left_moments_ago(now)

    def vet_duo_navigation(self, request: NavigationHop) -> None:
        """Forget the site unless this top-level navigation to Duo came straight from it.

        Args:
            request: The tab's main-frame navigation request to a Duo URL, as its
                last redirect hop so far.
        """
        if not is_straight_from(request, self.site, is_in_prompt=self.is_top_level_duo):
            self.site = None

    def _left_moments_ago(self, now: float) -> bool:
        """True when the tab left Duo within the same-prompt window."""
        if self.left_duo_at is None:
            return False
        return now - self.left_duo_at < self.same_prompt_window_s


def is_straight_from(request: NavigationHop, site: str | None, *, is_in_prompt: bool) -> bool:
    """True when `request`'s redirect chain stays on Duo or `site` and was started by `site`.

    Args:
        request: A navigation request (its last hop so far).
        site: The tab's site, or None.
        is_in_prompt: Whether the tab's top-level page is already on Duo, so a
            Referer on Duo (a hop inside the prompt) counts too.

    Returns:
        False for no site, for a hop on any other host or one whose host can't be
        read, and unless the chain's first request carries a Referer on `site` (or
        on Duo, when is_in_prompt). A missing or unreadable Referer is False.
    """
    if site is None:
        return False
    hops = _redirect_chain(request)
    if not all(_is_on_duo_or(hop.url, site) for hop in hops):
        return False
    # The first request's Referer names the page that started the navigation (a redirect's
    # Referrer-Policy can strip it from later hops). None: nothing was sent (Claude's
    # navigate, a page with a no-referrer policy) or it can't be read.
    referer_host = host_of(hops[0].headers.get("referer", ""))
    if referer_host is None:
        return False
    return referer_host == site or (is_in_prompt and is_duo_host(referer_host))


def _redirect_chain(request: NavigationHop) -> list[NavigationHop]:
    """Every hop of `request`'s redirect chain, the first request first."""
    hops: list[NavigationHop] = []
    hop: NavigationHop | None = request
    while hop is not None:
        hops.append(hop)
        hop = hop.redirected_from
    return hops[::-1]


def _is_on_duo_or(url: str, site: str) -> bool:
    """True when `url`'s host can be read and is `site` or a Duo host."""
    host = host_of(url)
    return host is not None and (host == site or is_duo_host(host))
