"""live_secret_values: retries while a navigation destroys the frames, and never hangs (fakes)."""

import asyncio

import pytest
from playwright.async_api import Error as PlaywrightError

from browser_tool.actions import ActionError, TabReadError, scrub_secrets
from browser_tool.actions.secret_scrub import SCRUB_REFUSAL, scrub_or_refuse
from browser_tool.redaction import live_secret_values, value_scrub


class FakeFrame:
    """A frame whose first `fails` reads raise, as when Enter's form post commits mid-read."""

    def __init__(self, values: list[str], fails: int, url: str = "https://a.example/") -> None:
        self.values, self.fails, self.url = values, fails, url
        self.hangs = False

    def is_detached(self) -> bool:
        return False

    def locator(self, selector: str) -> "FakeFrame":
        return self

    async def evaluate_all(self, script: str) -> list[str]:
        if self.hangs:
            await asyncio.Event().wait()  # never answers, like Edge's PDF viewer did
        if self.fails:
            self.fails -= 1
            raise PlaywrightError("Execution context was destroyed")
        return self.values


class FakePage:
    def __init__(self, *frames: FakeFrame) -> None:
        self.frames = list(frames)
        self.waits = 0

    async def wait_for_load_state(self, state: str, timeout: float) -> None:
        self.waits += 1


@pytest.mark.asyncio
async def test_a_navigation_mid_read_is_retried_then_fails_closed():
    page = FakePage(FakeFrame(["pw-after-submit"], fails=2))
    assert await live_secret_values(page) == {"pw-after-submit"}
    assert page.waits == 2

    with pytest.raises(PlaywrightError):  # still failing after every retry: callers withhold
        await live_secret_values(FakePage(FakeFrame([], fails=3)))


def hanging(url: str) -> FakeFrame:
    frame = FakeFrame([], fails=0, url=url)
    frame.hangs = True
    return frame


@pytest.mark.asyncio
async def test_a_frame_that_never_answers_fails_the_scrub_closed_instead_of_hanging(
    make_ctx, monkeypatch
):
    monkeypatch.setattr(value_scrub, "FRAME_READ_TIMEOUT_S", 0.1)
    viewer = hanging("chrome-extension://pdf-viewer/index.html")  # skipped: no page fields
    assert await live_secret_values(FakePage(FakeFrame(["pw-1"], 0), viewer)) == {"pw-1"}

    ctx = await make_ctx()  # no browser launched; the scrub reads the fake tab
    monkeypatch.setattr(ctx.session, "pages", lambda: [FakePage(hanging("https://a.example/"))])
    with pytest.raises(ActionError) as refusal:
        await asyncio.wait_for(scrub_or_refuse(ctx, ["text"]), timeout=2)
    assert str(refusal.value) == SCRUB_REFUSAL
    with pytest.raises(TabReadError) as failed:  # the tool runner names the tab to close
        await scrub_secrets(ctx, ["text"])
    assert failed.value.tab_index == 0
