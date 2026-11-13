"""SnapshotCache: each tab's latest redacted snapshot, for paging, subtrees and find.

Only text the snapshot tool already redacted is stored, so serving from here
can't show more than a full snapshot would. An entry is dropped when its tab's
main frame navigates (any framenavigated, same-document ones too) and replaced
by each new snapshot. Keys are weak, so closed tabs don't pile up.
"""

import weakref
from collections.abc import Callable
from dataclasses import dataclass

from playwright.async_api import Frame, Page


@dataclass(frozen=True)
class CachedSnapshot:
    """One tab's redacted snapshot and the header it was taken under.

    Attributes:
        url: The page URL when it was taken (raw; only compared, never shown).
        shown_url: The same as shown (secret_scrub.shown_url).
        title: The page title (page-supplied, shown only as untrusted content).
        text: The redacted aria snapshot.
    """

    url: str
    shown_url: str
    title: str
    text: str


class SnapshotCache:
    """Per-tab latest snapshot, dropped on navigation."""

    def __init__(self) -> None:
        """Start empty."""
        self._by_page: weakref.WeakKeyDictionary[Page, CachedSnapshot] = weakref.WeakKeyDictionary()
        self._watched: weakref.WeakSet[Page] = weakref.WeakSet()

    def store(self, page: Page, snapshot: CachedSnapshot) -> None:
        """Keep `snapshot` as `page`'s latest, replacing the one before."""
        if page not in self._watched:
            self._watched.add(page)
            page.on("framenavigated", self._drop_on_navigation(page))
        self._by_page[page] = snapshot

    def get(self, page: Page) -> CachedSnapshot | None:
        """The page's latest snapshot, or None if there is none or the page moved since.

        The URL check backs up the navigation listener, so a missed event can't
        serve another page's snapshot.
        """
        cached = self._by_page.get(page)
        if cached is None or cached.url != page.url:
            return None
        return cached

    def _drop_on_navigation(self, page: Page) -> Callable[[Frame], None]:
        """A framenavigated handler that drops `page`'s entry when its main frame moves.

        It holds the page weakly, so the listener doesn't keep a closed tab alive.
        """
        page_ref = weakref.ref(page)

        def on_navigated(frame: Frame) -> None:
            watched = page_ref()
            if watched is not None and frame == watched.main_frame:
                self._by_page.pop(watched, None)

        return on_navigated
