"""FileChooserWatch: no native file picker ever opens on the owner's screen.

Playwright intercepts a tab's file picker as soon as the tab has a
"filechooser" listener, so every tab of each context gets one. A picker the
page opens on its own (a click on "Attach") is dropped, which leaves the file
input unchanged, and noted for the next result, so the model knows to use
upload_file. upload_file claims the next picker of its tab instead, and sets
its file there. A tab is only covered once Playwright has sent the intercept
to it, a moment after the tab opens.
"""

import asyncio
import logging
import weakref

from playwright.async_api import BrowserContext, FileChooser, Page

logger = logging.getLogger(__name__)


class FileChooserWatch:
    """Intercepts every tab's file pickers and hands a claimed one to upload_file."""

    def __init__(self) -> None:
        """Start with no claims and nothing noted."""
        self._claims: weakref.WeakKeyDictionary[Page, asyncio.Future[FileChooser]] = (
            weakref.WeakKeyDictionary()
        )
        self._opened: list[Page] = []

    def watch(self, context: BrowserContext) -> None:
        """Intercept the pickers of every open and future tab of `context`."""
        for page in context.pages:
            self._watch_page(page)
        context.on("page", self._watch_page)

    def claim(self, page: Page) -> asyncio.Future[FileChooser]:
        """The next picker `page` opens goes to the returned future (and isn't noted)."""
        claim: asyncio.Future[FileChooser] = asyncio.get_running_loop().create_future()
        self._claims[page] = claim
        return claim

    def release(self, page: Page) -> None:
        """Drop `page`'s claim, answered or not."""
        self._claims.pop(page, None)

    def take_opened(self) -> list[Page]:
        """The tabs whose own pickers were dropped since the last call, one per picker."""
        opened, self._opened = self._opened, []
        return opened

    def _watch_page(self, page: Page) -> None:
        page.on("filechooser", self._on_chooser)

    def _on_chooser(self, chooser: FileChooser) -> None:
        claim = self._claims.pop(chooser.page, None)
        if claim is not None and not claim.done():
            claim.set_result(chooser)
            return
        logger.info("a file picker opened; intercepted and dropped")
        self._opened.append(chooser.page)
