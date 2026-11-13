"""Tests for the sleepmode MCP tools through an in-process mcp.Client, on a faked SleepMode."""

import asyncio
import time

import pytest
from mcp import Client
from support.fakes import make_rig

from sleepmode.mcp_server import SERVER_NAME, SleepTools, build_server


def _text(result) -> str:
    return "".join(block.text for block in result.content)


@pytest.mark.asyncio
async def test_voice_round_trip_and_readable_errors(tmp_path) -> None:
    rig = make_rig(tmp_path)
    async with Client(build_server(SleepTools(rig.sleep_mode))) as client:
        assert client.server_info.name == SERVER_NAME == "sleepmode"
        names = [tool.name for tool in (await client.list_tools()).tools]
        bad = await client.call_tool("sleep_mode_on", {"wake_at": "25:00"})
        on = await client.call_tool("sleep_mode_on", {"wake_at": "7am"})
        status = await client.call_tool("sleep_mode_status", {})
        off = await client.call_tool("sleep_mode_off", {})

    assert names == ["sleep_mode_on", "sleep_mode_off", "sleep_mode_status"]
    assert bad.is_error and "out of range" in _text(bad)
    assert not on.is_error and "07:00" in _text(on)
    assert "PROJ-1" in _text(status) and "night sky" in _text(status)
    assert not off.is_error and not rig.sleep_mode.status().state.is_asleep


@pytest.mark.asyncio
async def test_a_wake_waits_for_a_sleep_in_progress(tmp_path) -> None:
    # Regression: each call ran in its own worker thread with no lock, so a wake could
    # save "awake" over a sleep still in progress and leave its screens dark.
    rig = make_rig(tmp_path)
    events: list[str] = []
    sleep, wake = rig.sleep_mode.sleep, rig.sleep_mode.wake

    def slow_sleep(*args):
        events.append("sleep starts")
        time.sleep(0.2)
        events.append("sleep ends")
        return sleep(*args)

    def recorded_wake(*args):
        events.append("wake")
        return wake(*args)

    rig.sleep_mode.sleep, rig.sleep_mode.wake = slow_sleep, recorded_wake
    tools = SleepTools(rig.sleep_mode)
    sleeping = asyncio.create_task(tools.sleep_mode_on())
    await asyncio.sleep(0.05)
    await asyncio.gather(sleeping, tools.sleep_mode_off())
    assert events == ["sleep starts", "sleep ends", "wake"]
