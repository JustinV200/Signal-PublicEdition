"""upload_file on headless Edge: the send rule, both ways in, and no native file picker."""

from dataclasses import replace

import pytest
from support.browser_helpers import ALLOWED_HOST, ref_for

from browser_tool import actions
from browser_tool.actions import ActionError, navigate, snapshot, upload_file
from browser_tool.config import UploadSettings
from browser_tool.server import ToolRunner

PAGE = "/dialogs.html"
INPUT = 'button "Attachment"'
BUTTON = 'button "Attach"'

ROWS = {
    "file_input_approved": (INPUT, True, True, "got notes.txt:hello"),
    "upload_button_approved": (BUTTON, True, True, "got notes.txt:hello"),
    "declined": (INPUT, False, True, "not done"),
    "docker_server": (INPUT, True, False, "uploads are off"),
}


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "answer", "allowed", "expected"), ROWS.values(), ids=ROWS.keys())
async def test_upload_file_always_asks_as_a_send(
    make_ctx, fixture_server, tmp_path, label, answer, allowed, expected
):
    ctx = await make_ctx(answer=answer)
    ctx.settings = replace(ctx.settings, uploads=UploadSettings(roots=(str(tmp_path),)))
    ctx.uploads_allowed = allowed
    (tmp_path / "notes.txt").write_text("hello")
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, PAGE))
    text = await snapshot(ctx)
    page = await ctx.session.current_page()
    ref = ref_for(text, label)

    if expected.startswith("got"):
        result = await upload_file(ctx, ref, str(tmp_path / "notes.txt"))
        assert result.startswith("uploaded notes.txt (5 bytes)")
        await page.wait_for_function("document.getElementById('status').textContent !== 'idle'")
    else:
        with pytest.raises(ActionError, match=expected):
            await upload_file(ctx, ref, str(tmp_path / "notes.txt"))
        expected = "idle"
    assert await page.locator("#status").inner_text() == expected
    asked = [request.action for request in ctx.confirmer.requests]
    assert asked == ([] if not allowed else [asked[0]])
    assert not allowed or "notes.txt (5 bytes)" in asked[0]


@pytest.mark.asyncio
async def test_a_page_opened_file_picker_is_dropped_and_noted(make_ctx, fixture_server):
    ctx = await make_ctx()
    runner = ToolRunner(ctx)
    await runner.run("navigate", actions.navigate, fixture_server.url(ALLOWED_HOST, PAGE))
    text = await runner.run("snapshot", actions.snapshot)

    result = await runner.run("click", actions.click, ref_for(text, 'button "Attach"'))
    assert "tab 0 opened a file picker, which was closed without a file" in result
    page = await ctx.session.current_page()
    assert await page.locator("#file").evaluate("el => el.files.length") == 0
