"""`FilledRegistry`: which elements the vault filled on which page, and with what.

`has_filled_fields` uses the handles to block snapshots and screenshots while a
filled field is still on the page. `scrub` uses the secrets to redact text the
browser tool is about to return; they stay for the page's whole life, because
a username often reappears after login ("Signed in as ..."). Everything for a
page is dropped when it closes, and pages are held weakly.
"""

import weakref
from dataclasses import dataclass, field
from typing import Any

from vault.fill.page_protocol import ElementLike, PageLike
from vault.secret import Secret

PAGE_CLOSE_EVENT = "close"


@dataclass
class _PageEntry:
    """What the vault filled on one page."""

    live_handles: list[ElementLike] = field(default_factory=list)
    secrets: list[Secret] = field(default_factory=list)


class FilledRegistry:
    """Per-page record of vault-filled fields. Holds secrets only inside `Secret` wrappers."""

    def __init__(self) -> None:
        self._entries: weakref.WeakKeyDictionary[Any, _PageEntry] = weakref.WeakKeyDictionary()

    def register(self, page: PageLike, handle: ElementLike, secret: Secret) -> None:
        """Remember that `handle` on `page` is about to be filled with `secret`.

        Call this before filling, so a partly failed fill is still blocked and scrubbed.
        """
        entry = self._entries.get(page)
        if entry is None:
            entry = _PageEntry()
            self._entries[page] = entry
            self._forget_on_close(page)
        entry.live_handles.append(handle)
        entry.secrets.append(secret)

    def _forget_on_close(self, page: PageLike) -> None:
        # A weak reference, so the close callback doesn't keep the page alive.
        page_ref = weakref.ref(page)

        def forget_closed_page(*_event_args: object) -> None:
            closed_page = page_ref()
            if closed_page is not None:
                self.forget(closed_page)

        page.once(PAGE_CLOSE_EVENT, forget_closed_page)

    def handles(self, page: PageLike) -> list[ElementLike]:
        """Return the filled handles on `page` that may still be attached."""
        entry = self._entries.get(page)
        return list(entry.live_handles) if entry else []

    def drop_handle(self, page: PageLike, handle: ElementLike) -> None:
        """Stop checking `handle` (its element is gone). Its secret is kept for scrubbing."""
        entry = self._entries.get(page)
        if entry is not None:
            entry.live_handles = [kept for kept in entry.live_handles if kept is not handle]

    def secrets(self) -> list[Secret]:
        """Return every secret filled on any page that is still open."""
        return [secret for entry in self._entries.values() for secret in entry.secrets]

    def forget(self, page: PageLike) -> None:
        """Drop everything recorded for `page` (called when it closes)."""
        self._entries.pop(page, None)
