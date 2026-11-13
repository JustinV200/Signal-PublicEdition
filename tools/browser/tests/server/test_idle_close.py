"""IdleClose's generation check, with a fake close (no browser)."""

import asyncio

import pytest

from browser_tool.server.idle_close import IdleClose

IDLE_S = 0.02


@pytest.mark.asyncio
async def test_a_call_that_slipped_in_after_the_timer_fired_keeps_the_browser():
    closes = []

    async def close() -> None:
        closes.append(1)

    lock = asyncio.Lock()
    idle = IdleClose(IDLE_S, lock, close)
    idle.arm()
    async with lock:  # a tool call that started just as the timer fired
        await asyncio.sleep(IDLE_S * 3)
        idle.cancel()
        idle.arm()
    await asyncio.sleep(0)  # the fired close gets the lock, sees a new generation
    assert closes == []

    await asyncio.sleep(IDLE_S * 5)  # then a real quiet spell
    assert closes == [1]
