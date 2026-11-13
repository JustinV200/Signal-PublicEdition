"""Page dialogs on headless Edge: answer_dialog's gate, prompt text, and how results show them."""

import asyncio
from typing import NamedTuple

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from support.browser_helpers import ALLOWED_HOST, ref_for

from browser_tool import actions
from browser_tool.actions import ActionError, answer_dialog, click, navigate, snapshot
from browser_tool.server import ToolRunner

PAGE = "/dialogs.html"
SECRET = "hunter2-secret-xyz"


class Row(NamedTuple):
    """Click `button`, then answer its dialog; the owner says no to anything that asks."""

    name: str
    button: str
    accept: bool
    text: str | None
    asks: bool
    status: str  # #status afterwards ("idle": nothing happened)
    refused: str | None = None
    double: bool = False


ROWS = [
    Row("accept_delete_message", "Clear inbox", True, None, True, "idle", "not done"),
    Row("dismiss_never_asks", "Clear inbox", False, None, False, "kept"),
    Row("accept_plain_confirm", "Tidy up", True, None, False, "tidied"),
    # A bare "Are you sure?" is judged with the clicked "Remove draft".
    Row("accept_after_a_delete_click", "Remove draft", True, None, True, "idle", "not done"),
    Row("accept_pay_message", "Finish", True, None, True, "idle", "not done"),
    Row("prompt_with_text", "Rename", True, "notes", False, "renamed:notes"),
    Row("prompt_preset_text", "Rename", True, None, False, "renamed:old"),
    Row("pin_prompt_text", "Change PIN", True, "1234", False, "idle", "PIN or code"),
    Row("pin_prompt_dismissed", "Change PIN", False, None, False, "pin:null"),
    Row("text_on_a_confirm", "Tidy up", True, "x", False, "idle", "only with accept=true"),
    Row("text_with_dismiss", "Rename", False, "x", False, "idle", "only with accept=true"),
    # The double click's second half must not press again once the dialog is answered.
    Row("double_click_opens_one_dialog", "Tidy up", False, None, False, "kept", double=True),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("row", ROWS, ids=[row.name for row in ROWS])
async def test_answer_dialog_gates_accepts_on_message_and_trigger(make_ctx, fixture_server, row):
    ctx = await make_ctx(answer=True)
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, PAGE))
    text = await snapshot(ctx)
    page = await ctx.session.current_page()
    assert "dialog" in await click(ctx, ref_for(text, f'button "{row.button}"'), double=row.double)
    asked_before = len(ctx.confirmer.requests)
    ctx.confirmer.answer = False

    if row.refused:
        with pytest.raises(ActionError, match=row.refused):
            await answer_dialog(ctx, row.accept, row.text)
        assert ctx.session.dialogs.pending(page) is not None  # still open to answer
        await answer_dialog(ctx, False)  # unfreeze the tab to read it
        assert await page.locator("#status").inner_text() in ("kept", "pin:null", "renamed:null")
    else:
        result = await answer_dialog(ctx, row.accept, row.text)
        assert result.startswith("accepted" if row.accept else "dismissed")
        assert await page.locator("#status").inner_text() == row.status
    assert len(ctx.confirmer.requests) - asked_before == int(row.asks)
    await asyncio.sleep(0.3)  # time for a second half to (wrongly) open another one
    assert ctx.session.dialogs.pending(page) is None


@pytest.mark.asyncio
async def test_an_open_dialog_freezes_the_tab_and_shows_in_every_result(
    make_ctx, fixture_server, caplog
):
    ctx = await make_ctx()
    runner = ToolRunner(ctx)
    await runner.run("navigate", actions.navigate, fixture_server.url(ALLOWED_HOST, PAGE))
    page = await ctx.session.current_page()
    await page.locator("#pw").fill(SECRET)  # the owner typed it; the page echoes it
    text = await runner.run("snapshot", actions.snapshot)

    hi = await runner.run("click", actions.click, ref_for(text, 'button "Say hi"'))
    assert "showed an alert, which was accepted" in hi and "hello there" in hi
    spam = await runner.run("click", actions.click, ref_for(text, 'button "Spam"'))
    assert "spam 4" in spam and "spam 5" not in spam and "and 3 more alerts" in spam
    echoed = await runner.run("click", actions.click, ref_for(text, 'button "Echo"'))
    assert "a confirm dialog is open on tab 0" in echoed
    assert SECRET not in echoed  # scrubbed from the values read before it froze
    assert "a dialog is open on this tab" in await runner.run("tabs", actions.list_tabs)
    frozen_calls = (
        ("snapshot", ()),
        ("screenshot", ()),
        ("navigate", (fixture_server.url(ALLOWED_HOST, PAGE),)),
    )
    for tool, args in frozen_calls:
        with pytest.raises(ToolError, match="dialog is open on this tab") as refused:
            await runner.run(tool, getattr(actions, tool), *args)
        assert SECRET not in str(refused.value)
    assert "dismissed the confirm dialog" in await runner.run(
        "answer_dialog", actions.answer_dialog, False
    )
    assert await page.locator("#status").inner_text() == "kept"
    assert SECRET not in caplog.text and "Your password" not in caplog.text


@pytest.mark.asyncio
async def test_a_tool_stuck_on_a_dialog_it_did_not_act_for_is_stopped(make_ctx, fixture_server):
    ctx = await make_ctx(answer=True)
    runner = ToolRunner(ctx)
    await runner.run("navigate", actions.navigate, fixture_server.url(ALLOWED_HOST, PAGE))
    text = await runner.run("snapshot", actions.snapshot)

    # The click's hover opens a confirm, which freezes the gate's look at the button.
    click_trap = runner.run("click", actions.click, ref_for(text, 'button "Hover trap"'))
    with pytest.raises(ToolError, match="stopped: the page opened a confirm dialog while click"):
        await asyncio.wait_for(click_trap, timeout=5)
    assert "accepted the confirm dialog" in await runner.run(
        "answer_dialog", actions.answer_dialog, True
    )
