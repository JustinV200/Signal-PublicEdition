"""Downloads: the policy check (fakes), and on headless Edge saving, reporting and the cap."""

import asyncio

import pytest
from support.browser_helpers import ALLOWED_HOST, BLOCKED_HOST, ref_for

from browser_tool.actions import UNTRUSTED_OPEN, click, download_notes, navigate, snapshot
from browser_tool.config import DownloadSettings
from browser_tool.downloads import INCOMING_FOLDER_NAME, DownloadRecorder, recorder
from browser_tool.policy import HostPolicy

ALLOWED_PAGE = f"http://{ALLOWED_HOST}/page.html"
BLOCKED_PAGE = f"http://{BLOCKED_HOST}/page.html"


class FakePage:
    def __init__(self, url):
        self.url = url
        self.handlers = []

    def on(self, event, handler):
        self.handlers.append(handler)


class FakeContext:
    def __init__(self, page):
        self.pages = [page]

    def on(self, event, handler):
        pass


class FakeDownload:
    """A download that ends as interrupted unless cancelled first; records the cancel."""

    suggested_filename = "notes.txt"

    def __init__(self, url, page):
        self.url = url
        self.page = page
        self.is_cancelled = False

    async def cancel(self):
        self.is_cancelled = True

    async def failure(self):
        return "interrupted"


class StalledDownload(FakeDownload):
    """Never makes progress; ends only when cancelled."""

    def __init__(self, url, page):
        super().__init__(url, page)
        self._ended = asyncio.Event()

    async def cancel(self):
        self.is_cancelled = True
        self._ended.set()

    async def failure(self):
        await self._ended.wait()
        return "canceled"


def _watched_recorder(tmp_path, page):
    policy = HostPolicy.from_strings((ALLOWED_HOST,), ())
    downloads = DownloadRecorder(DownloadSettings(folder=str(tmp_path / "saved")), policy)
    downloads.watch(FakeContext(page), tmp_path / "incoming")
    return downloads


@pytest.mark.asyncio
async def test_a_stalled_download_holds_up_no_later_call_and_is_cancelled(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "STALL_S", 0.5)
    page = FakePage(ALLOWED_PAGE)
    downloads = _watched_recorder(tmp_path, page)
    download = StalledDownload(f"http://{ALLOWED_HOST}/f.txt", page)
    page.handlers[0](download)
    # A later call (started_before=1) doesn't wait for it: running, reported later.
    assert await asyncio.wait_for(downloads.collect(1, 30), 0.2) == ([], 1)
    [result], running = await downloads.collect(0, 5)
    assert (result.problem, running) == (recorder.STALLED, 0)
    assert download.is_cancelled


@pytest.mark.parametrize(
    ("url", "page_url", "is_allowed"),
    [
        (f"http://{BLOCKED_HOST}/f.txt", ALLOWED_PAGE, False),
        (f"blob:http://{ALLOWED_HOST}/uuid", BLOCKED_PAGE, False),
        ("blob:null/uuid", "about:blank", False),
        ("data:text/plain,hi", "about:blank", False),
        (f"blob:http://{ALLOWED_HOST}/uuid", ALLOWED_PAGE, True),
        (f"http://{ALLOWED_HOST}/f.txt", "about:blank", True),
    ],
)
@pytest.mark.asyncio
async def test_download_source_must_pass_the_policy(tmp_path, url, page_url, is_allowed):
    page = FakePage(page_url)
    downloads = _watched_recorder(tmp_path, page)
    download = FakeDownload(url, page)
    [handler] = page.handlers
    handler(download)
    [result], running = await downloads.collect(0, 5)
    assert running == 0
    assert download.is_cancelled is not is_allowed
    assert result.problem.startswith("it came from") is not is_allowed


@pytest.mark.asyncio
async def test_navigate_to_a_download_saves_it_and_reports_it(make_ctx, fixture_server, tmp_path):
    ctx = await make_ctx()
    url = fixture_server.url(ALLOWED_HOST, "/download?name=../lab.ipynb&kb=3")
    for _ in range(2):
        result = await navigate(ctx, url)
        assert "started a download" in result
        assert "navigation failed" not in result
        [note] = await download_notes(ctx, 0)
        assert note.startswith(f"download saved (3072 bytes): {UNTRUSTED_OPEN}")
    folder = tmp_path / "downloads"
    # The server's name had a folder in it; the clash got a counter, nothing was overwritten.
    assert sorted(path.name for path in folder.iterdir()) == ["_lab (1).ipynb", "_lab.ipynb"]
    assert str(folder / "_lab (1).ipynb") in note
    assert (folder / "_lab.ipynb").read_bytes() == b"x" * 3072
    assert await download_notes(ctx, 0) == []  # reported once


@pytest.mark.asyncio
async def test_download_over_the_cap_is_cancelled_and_nothing_is_kept(
    make_ctx, fixture_server, tmp_path
):
    ctx = await make_ctx(downloads=DownloadSettings(folder=str(tmp_path / "downloads"), max_mb=1))
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/download?name=big.bin&kb=4096"))
    [note] = await download_notes(ctx, 0)
    assert note.startswith("download not saved: it is over the 1 MB limit")
    assert not (tmp_path / "downloads").exists()
    assert list((tmp_path / "profile" / INCOMING_FOLDER_NAME).iterdir()) == []


@pytest.mark.asyncio
async def test_a_click_that_starts_a_download_is_reported(make_ctx, fixture_server, tmp_path):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/download.html"))
    before = ctx.session.downloads.started
    await click(ctx, ref_for(await snapshot(ctx), "Get the notebook"))
    # The download event can come just after the click returns; the next result reports it.
    assert await ctx.session.downloads.wait_for_start(before, 5)
    [note] = await download_notes(ctx, 0)
    assert "lab.ipynb saved as" in note
    assert (tmp_path / "downloads" / "lab.ipynb").stat().st_size == 1024
