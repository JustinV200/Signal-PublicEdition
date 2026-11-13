"""ToolRunner error mapping and scrubbing, with fake actions (no browser launched)."""

import logging

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from playwright.async_api import Error as PlaywrightError
from support.browser_helpers import headless_settings
from support.fakes import FakeConfirmer, FakeLoginFiller

from browser_tool.actions import ActionContext, ActionError
from browser_tool.server import INTERNAL_ERROR, SCRUB_FAILED, SCRUB_FAILED_AFTER_ACTION, ToolRunner

SECRET = "runner-secret-77x"


def build_ctx(tmp_path, filler=None) -> ActionContext:
    return ActionContext.create(
        headless_settings(tmp_path), FakeConfirmer(), filler or FakeLoginFiller()
    )


def make_runner(tmp_path, filler=None) -> ToolRunner:
    return ToolRunner(build_ctx(tmp_path, filler))


async def returns(ctx, text):
    return text


async def raises(ctx, error):
    raise error


@pytest.mark.asyncio
async def test_playwright_error_text_is_neither_returned_nor_logged(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    error = PlaywrightError(f'Locator.fill: Timeout\nCall log:\n  - fill("{SECRET}")')
    with pytest.raises(ToolError) as raised:
        await make_runner(tmp_path).run("type_text", raises, error)
    assert SECRET not in str(raised.value)
    assert SECRET not in caplog.text


@pytest.mark.asyncio
async def test_unexpected_exception_is_generic_and_message_not_logged(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ToolError) as raised:
        await make_runner(tmp_path).run("t", raises, KeyError(SECRET))
    assert str(raised.value) == INTERNAL_ERROR
    assert SECRET not in caplog.text
    assert "KeyError" in caplog.text


class ExplodingScrubFiller(FakeLoginFiller):
    def scrub(self, page, text):
        raise RuntimeError("scrub broke")


class OneDuoNotice:
    """Stands in for DuoWatch: one queued notice, as after a tab entered Duo."""

    def __init__(self) -> None:
        self.notices = ["Tab 0 is showing a Duo two-factor prompt"]

    async def take_notices(self) -> list[str]:
        notices, self.notices = self.notices, []
        return notices


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "arg", "expected"),
    [
        (returns, SECRET, SCRUB_FAILED_AFTER_ACTION),  # the action ran: don't let the model redo it
        (raises, ActionError(SECRET), SCRUB_FAILED),
    ],
    ids=["action-ran", "action-failed"],
)
async def test_failed_scrub_withholds_the_text_but_keeps_the_duo_notice(
    tmp_path, action, arg, expected
):
    ctx = build_ctx(tmp_path, ExplodingScrubFiller())
    runner = ToolRunner(ctx)
    try:
        await ctx.session.start()  # scrub runs per open tab, so a tab must exist
        ctx.session.duo = OneDuoNotice()
        with pytest.raises(ToolError) as raised:
            await runner.run("t", action, arg)
        assert str(raised.value) == f"{expected}\n\nTab 0 is showing a Duo two-factor prompt"
    finally:
        await ctx.session.close()
