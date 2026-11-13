"""Voice self-heal between turns: only failed MCP servers are reconnected, a broken one is
retried after a cool-down, a failing probe never costs the turn, and a changed .mcp.json
reconnects resuming the conversation."""

import asyncio
import os

import pytest

from audiohub.brain import ReplyText, TurnDone
from audiohub.brain.connection import mcp_heal
from audiohub.brain.connection.mcp_heal import RETRY_AFTER_S, McpHealer

DONE = TurnDone(duration_s=1.0, cost_usd=0.01, is_error=False)


class StatusSession:
    """Just the two MCP calls the healer makes. None statuses fail the probe; `broken` servers
    fail to reconnect, and `hung` ones never answer."""

    def __init__(
        self,
        statuses: dict[str, str] | None,
        broken: frozenset[str] = frozenset(),
        hung: frozenset[str] = frozenset(),
    ) -> None:
        self.statuses = statuses
        self.broken = broken
        self.hung = hung
        self.attempts: list[str] = []

    async def mcp_server_statuses(self) -> dict[str, str]:
        if self.statuses is None:
            raise Exception("control request timed out")  # what the SDK raises
        return self.statuses

    async def reconnect_mcp_server(self, name: str) -> None:
        self.attempts.append(name)
        if name in self.hung:
            await asyncio.Event().wait()
        if name in self.broken:
            raise Exception(f"{name} exited at start")


@pytest.mark.asyncio
async def test_only_failed_servers_are_reconnected_and_a_broken_one_waits() -> None:
    now = [0.0]
    healer = McpHealer(clock=lambda: now[0])
    statuses = {"mail": "failed", "sessions": "connected", "brief": "pending", "x": "failed"}
    session = StatusSession(statuses, broken=frozenset({"x"}))

    await healer.heal(session)  # type: ignore[arg-type]
    now[0] = RETRY_AFTER_S - 1
    await healer.heal(session)  # type: ignore[arg-type]
    now[0] = 2 * RETRY_AFTER_S
    await healer.heal(session)  # type: ignore[arg-type]

    # mail is still reported failed each time, so it's retried each time; x waits.
    assert session.attempts == ["mail", "x", "mail", "mail", "x"]


@pytest.mark.asyncio
async def test_a_failing_status_probe_never_raises() -> None:
    session = StatusSession(None)
    await McpHealer().heal(session)  # type: ignore[arg-type]
    assert session.attempts == []


@pytest.mark.asyncio
async def test_a_hung_reconnect_times_out_and_cools_down(monkeypatch) -> None:
    monkeypatch.setattr(mcp_heal, "CALL_TIMEOUT_S", 0.01)
    healer = McpHealer(clock=lambda: 0.0)
    session = StatusSession({"browser": "failed"}, hung=frozenset({"browser"}))

    await asyncio.wait_for(healer.heal(session), 1)  # type: ignore[arg-type]
    await asyncio.wait_for(healer.heal(session), 1)  # type: ignore[arg-type]

    assert session.attempts == ["browser"]  # the timeout started the cool-down


@pytest.mark.asyncio
async def test_stop_during_a_slow_heal_means_the_request_is_never_sent(brain_kit) -> None:
    harness = brain_kit.Harness([[ReplyText("Deleted it."), DONE]])
    reconnecting, release = asyncio.Event(), asyncio.Event()

    async def slow_reconnect(name: str) -> None:
        reconnecting.set()
        await release.wait()

    async with harness.brain as brain:
        harness.session.mcp_statuses = {"mail": "failed"}
        harness.session.reconnect_mcp_server = slow_reconnect
        asking = asyncio.create_task(brain_kit.collect(brain.ask("delete the branch")))
        await asyncio.wait_for(reconnecting.wait(), 1)
        await brain.interrupt()
        release.set()
        [done] = await asyncio.wait_for(asking, 1)

    assert harness.session.sent == []
    assert isinstance(done, TurnDone) and done.is_error


@pytest.mark.asyncio
async def test_brain_heals_before_a_turn_and_reconnects_on_a_new_mcp_config(
    brain_kit, tmp_path
) -> None:
    mcp_config = tmp_path / ".mcp.json"
    mcp_config.write_text("{}", encoding="utf-8")
    harness = brain_kit.Harness([[ReplyText("one"), DONE], [ReplyText("two"), DONE]], cwd=tmp_path)
    async with harness.brain as brain:
        first = harness.session
        first.mcp_statuses = {"mail": "failed", "sessions": "connected"}
        await brain_kit.collect(brain.ask("first"))
        first.session_id = "conv-1"
        stat = mcp_config.stat()
        os.utime(mcp_config, (stat.st_atime, stat.st_mtime + 10))  # a server was added

        second = await brain_kit.collect(brain.ask("second"))

    assert first.mcp_reconnected == ["mail"]
    assert second == [ReplyText("two"), DONE]
    assert len(harness.sessions) == 2
    assert harness.session.resumed == "conv-1"
