"""Save the desktop browser's downloads into the downloads folder, within the size cap.

The session hands every context whose backend accepts downloads to watch(). Each
"download" event on any of its tabs starts a background save:
1. The source must pass the host policy: the download's own URL (Playwright
   gives the final URL, after redirects), or for a blob: or data: download the
   page that made it. Routing already blocks a non-allowed URL; this is defence
   in depth, not the only check.
2. While it runs, the incoming folder is watched. A download past
   [downloads] max_mb, with no progress for STALL_S, or running past
   MAX_DOWNLOAD_S is cancelled (Edge deletes the partial file; launch clears
   any leftover).
3. A finished download is copied to a safe, unique name in the downloads folder
   (browser_tool.downloads.file_names). Playwright's copy is deleted either way.
A download is never opened, run or unpacked. Logs name the source origin and the
size, never the file name, which is page-supplied. Actions report the results
through collect(); wait_for_start() lets navigate tell a download from a failed load.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import BrowserContext, Download, Page
from playwright.async_api import Error as PlaywrightError

from browser_tool.config import DownloadSettings, resolve_tool_path
from browser_tool.downloads.file_names import reserve_path, safe_file_name
from browser_tool.downloads.incoming import file_sizes, remove_files_over
from browser_tool.policy import OPAQUE_SCHEMES, HostPolicy, origin_of, scheme_of

logger = logging.getLogger(__name__)

BYTES_PER_MB = 1024 * 1024
SIZE_POLL_S = 0.25
START_POLL_S = 0.05
# A download whose files haven't grown for this long is cancelled.
STALL_S = 60.0
# Nor may one trickle on for longer than this.
MAX_DOWNLOAD_S = 30 * 60.0
FAILED = "the download failed"
OVER_CAP = "it is over the {max_mb:g} MB limit ([downloads] max_mb); cancelled and deleted"
STALLED = f"it made no progress for {STALL_S:g} s; cancelled"
TOO_SLOW = f"it ran for more than {MAX_DOWNLOAD_S / 60:g} minutes; cancelled"
BLOCKED = "it came from {origin}, which is not on an allowed origin"


@dataclass(frozen=True)
class SavedDownload:
    """What became of one download.

    Attributes:
        original_name: The name the server or page suggested (untrusted page data).
        path: Where it was saved, or None when it wasn't.
        size_bytes: Its size once saved.
        problem: Why it wasn't saved (our own text), or None when it was.
    """

    original_name: str
    path: Path | None = None
    size_bytes: int = 0
    problem: str | None = None


@dataclass
class _Progress:
    """When a running download started, and when the incoming files last grew."""

    started_at: float
    changed_at: float
    total_bytes: int = 0


class DownloadRecorder:
    """Saves each download of the watched contexts and keeps the results for collect()."""

    def __init__(self, settings: DownloadSettings, policy: HostPolicy):
        """Args: settings: [downloads] (folder, max_mb). policy: Checks each download's source."""
        self._policy = policy
        self._folder = resolve_tool_path(settings.folder)
        self._max_bytes = settings.max_mb * BYTES_PER_MB
        self._over_cap = OVER_CAP.format(max_mb=settings.max_mb)
        self._incoming: Path | None = None
        # (start number, save task); start numbers count from 1, like `started`.
        self._pending: list[tuple[int, asyncio.Task[SavedDownload]]] = []
        # How many downloads have started; callers compare it before and after.
        self.started = 0

    def watch(self, context: BrowserContext, incoming: Path) -> None:
        """Save the downloads of every open and future tab of `context`.

        Args:
            context: A browser context launched with accept_downloads.
            incoming: Its downloads_path, where Edge writes in-flight downloads.
        """
        self._incoming = incoming
        for page in context.pages:
            self._watch_page(page)
        context.on("page", self._watch_page)

    async def wait_for_start(self, started_before: int, timeout_s: float) -> bool:
        """Wait until `started` passes `started_before`; False on timeout or when not watching.

        Playwright fails page.goto with "Download is starting" a moment before
        the download event arrives, so navigate waits here.
        """
        if self._incoming is None:
            return False
        deadline = asyncio.get_running_loop().time() + timeout_s
        while self.started <= started_before:
            if asyncio.get_running_loop().time() >= deadline:
                return False
            await asyncio.sleep(START_POLL_S)
        return True

    async def collect(
        self, started_before: int, timeout_s: float
    ) -> tuple[list[SavedDownload], int]:
        """Return the finished downloads once, waiting only for the ones this call started.

        Args:
            started_before: `started` when the tool call began. Downloads that
                started after it are waited for up to `timeout_s`; older ones
                aren't, so one slow download can't hold up every later call.
            timeout_s: The longest wait.

        Returns:
            The downloads that finished since the last collect, in start order,
            and how many are still running (a later collect returns them). Never raises.
        """
        fresh = [task for number, task in self._pending if number > started_before]
        if fresh:
            await asyncio.wait(fresh, timeout=timeout_s)
        finished = [task for _number, task in self._pending if task.done()]
        self._pending = [(number, task) for number, task in self._pending if not task.done()]
        # A task is only cancelled when its loop shuts down; there is nothing to report.
        results = [task.result() for task in finished if not task.cancelled()]
        return results, len(self._pending)

    def _watch_page(self, page: Page) -> None:
        page.on("download", self._on_download)

    def _on_download(self, download: Download) -> None:
        self.started += 1
        self._pending.append((self.started, asyncio.ensure_future(self._save_safely(download))))

    async def _save_safely(self, download: Download) -> SavedDownload:
        """_save, with any error turned into a FAILED result (collect must never raise)."""
        name = download.suggested_filename
        try:
            return await self._save(download, name)
        except Exception as error:  # noqa: BLE001 - reported as FAILED; Playwright text unsafe
            logger.warning("download failed: %s", type(error).__name__)
            return SavedDownload(name, problem=FAILED)

    async def _save(self, download: Download, name: str) -> SavedDownload:
        is_page_made = scheme_of(download.url) in OPAQUE_SCHEMES
        source_url = download.page.url if is_page_made else download.url
        source = origin_of(source_url)
        if not self._policy.check_url(source_url).is_allowed:
            logger.info("download from %s cancelled: not allowed", source)
            await download.cancel()
            return SavedDownload(name, problem=BLOCKED.format(origin=source))
        problem = await self._finish_watched(download)
        if problem is None:
            try:
                return await self._keep(download, name, source)
            finally:
                await _delete_temporary(download)
        logger.info("download from %s not saved: %s", source, problem)
        return SavedDownload(name, problem=problem)

    async def _keep(self, download: Download, name: str, source: str) -> SavedDownload:
        """Copy a finished download to a safe, unique name; refuse it when over the cap."""
        if (await download.path()).stat().st_size > self._max_bytes:
            logger.info("download from %s not saved: over the cap", source)
            return SavedDownload(name, problem=self._over_cap)
        target = reserve_path(self._folder, safe_file_name(name))
        try:
            await download.save_as(target)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        size = target.stat().st_size
        logger.info("download from %s saved: %d bytes", source, size)
        return SavedDownload(name, target, size)

    async def _finish_watched(self, download: Download) -> str | None:
        """Wait for the download to end; cancel it when _running_problem finds one.

        Returns:
            None when it finished whole, else the problem.
        """
        assert self._incoming is not None
        finished = asyncio.ensure_future(download.failure())
        now = asyncio.get_running_loop().time()
        progress = _Progress(started_at=now, changed_at=now)
        while True:
            done, _ = await asyncio.wait({finished}, timeout=SIZE_POLL_S)
            if done:
                return FAILED if finished.result() is not None else None
            problem = self._running_problem(progress)
            if problem is not None:
                await download.cancel()
                await finished  # a cancel ends it as "canceled"
                await remove_files_over(self._incoming, self._max_bytes)
                return problem

    def _running_problem(self, progress: _Progress) -> str | None:
        """Why a running download must stop now (over the cap, stalled, too long), or None.

        shortcut: the incoming files are named by Edge's uuid, which Playwright
        doesn't expose, so all of them count for every running download: an
        over-cap file cancels each one, and any file growing counts as progress
        for each one. Fine while downloads come one at a time.
        """
        assert self._incoming is not None
        sizes = file_sizes(self._incoming)
        if max(sizes, default=0) > self._max_bytes:
            return self._over_cap
        now = asyncio.get_running_loop().time()
        if sum(sizes) != progress.total_bytes:
            progress.total_bytes, progress.changed_at = sum(sizes), now
        if now - progress.changed_at > STALL_S:
            return STALLED
        if now - progress.started_at > MAX_DOWNLOAD_S:
            return TOO_SLOW
        return None


async def _delete_temporary(download: Download) -> None:
    """Delete Playwright's copy of a finished download; a failure is logged."""
    try:
        await download.delete()
    except PlaywrightError as error:
        logger.warning("could not delete a download's temporary copy: %s", type(error).__name__)
