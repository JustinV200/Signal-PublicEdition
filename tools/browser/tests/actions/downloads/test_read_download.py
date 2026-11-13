"""read_download: only files in the downloads folder, PDFs and text only, capped and untrusted."""

from dataclasses import replace
from pathlib import Path

import pytest
import pytest_asyncio
from support.fakes import SECRET_PASSWORD
from support.local_files import make_pdf, no_disk

from browser_tool.actions import UNTRUSTED_OPEN, ActionError, read_download
from browser_tool.config import BrowserSettings

PDF_PAGES = ["first page text", "second page text", "third page text"]
# The path rules themselves are tested in tests/actions/local_files; these rows
# show read_download applies them with the downloads folder as the only root.


def outside_file(folder: Path) -> str:
    (folder.parent / "life.txt").write_text("x")
    return str(folder.parent / "life.txt")


PATH_ROWS = {
    "text_file": (lambda folder: str(folder / "notes.txt"), None),
    "outside_the_folder": (outside_file, "must come from"),
    "not_pdf_or_text": (lambda folder: str(folder / "setup.exe"), "reads only"),
}
# Refused before any filesystem call, like uploads.
LEXICAL_ROWS = {
    "unc_share": lambda folder: r"\\attacker.example\share\notes.txt",
}


@pytest_asyncio.fixture
async def ctx(make_ctx, tmp_path):
    """A context (no browser launched) whose downloads folder holds a few files."""
    context = await make_ctx()
    folder = tmp_path / "downloads"
    folder.mkdir()
    (folder / "notes.txt").write_text("hello from a download")
    (folder / "setup.exe").write_bytes(b"MZ")
    (folder / "report.pdf").write_bytes(make_pdf(PDF_PAGES))
    (folder / "broken.pdf").write_bytes(b"%PDF-1.4\n(secret-in-broken-pdf) garbage")
    return context


@pytest.mark.asyncio
@pytest.mark.parametrize(("make", "refused"), PATH_ROWS.values(), ids=PATH_ROWS.keys())
async def test_only_pdf_and_text_files_in_the_downloads_folder_are_read(
    ctx, tmp_path, make, refused
):
    path = make(tmp_path / "downloads")
    if refused is None:
        result = await read_download(ctx, path)
        assert result.startswith(UNTRUSTED_OPEN) and "hello from a download" in result
        return
    with pytest.raises(ActionError, match=refused):
        await read_download(ctx, path)


@pytest.mark.asyncio
@pytest.mark.parametrize("make", LEXICAL_ROWS.values(), ids=LEXICAL_ROWS.keys())
async def test_network_and_outside_paths_are_refused_without_touching_disk(
    ctx, tmp_path, monkeypatch, make
):
    path = make(tmp_path / "downloads")
    with no_disk(monkeypatch), pytest.raises(ActionError, match="refused"):
        await read_download(ctx, path)


@pytest.mark.asyncio
async def test_a_pdf_is_read_by_pages_capped_and_never_echoed_when_broken(ctx, tmp_path):
    folder = tmp_path / "downloads"
    report = str(folder / "report.pdf")

    second = await read_download(ctx, report, "2")
    assert "second page text" in second and "first page text" not in second
    assert "read pages 2-2 of 3" in second
    assert 'pages="3-3"' in await read_download(ctx, report, "1-2")
    for bad_pages in ("0", "1-21", "3-1", "x"):
        with pytest.raises(ActionError, match="bad pages"):
            await read_download(ctx, report, bad_pages)
    with pytest.raises(ActionError, match="no page 4"):
        await read_download(ctx, report, "4")

    ctx.settings = replace(ctx.settings, browser=BrowserSettings(max_snapshot_chars=20))
    assert "cut at 20 characters" in await read_download(ctx, report)

    with pytest.raises(ActionError, match="could not be read") as refusal:
        await read_download(ctx, str(folder / "broken.pdf"))
    assert "secret-in-broken-pdf" not in str(refusal.value)


@pytest.mark.asyncio
async def test_a_secret_straddling_the_cut_leaves_no_prefix_of_it(ctx, tmp_path):
    # Cut first and the scrub would no longer recognise the half left at the end.
    (tmp_path / "downloads" / "leak.txt").write_text("x" * 15 + SECRET_PASSWORD + " tail")
    ctx.settings = replace(ctx.settings, browser=BrowserSettings(max_snapshot_chars=20))
    await ctx.session.start()  # the vault's scrub runs per open tab
    result = await read_download(ctx, str(tmp_path / "downloads" / "leak.txt"))
    assert "cut at 20 characters" in result
    assert SECRET_PASSWORD[:5] not in result


@pytest.mark.asyncio
async def test_the_docker_server_refuses(ctx, tmp_path):
    ctx.downloads_readable = False
    with pytest.raises(ActionError, match="off in docker"):
        await read_download(ctx, str(tmp_path / "downloads" / "notes.txt"))
