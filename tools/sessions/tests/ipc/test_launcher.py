"""Tests for ensure_daemon: start the daemon only when nothing answers, then wait for it."""

import asyncio
import socket
from pathlib import Path

import pytest

from claude_sessions.config import Settings, daemon_token_file
from claude_sessions.ipc import DaemonStartError, encode_error, encode_ok, ensure_daemon
from claude_sessions.tokens import create_token_file


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


async def _answer_ping(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    await reader.readline()
    writer.write(encode_ok({"pid": 1}))
    await writer.drain()
    writer.close()


@pytest.mark.asyncio
async def test_spawns_the_daemon_once_and_waits_until_it_answers(tmp_path: Path) -> None:
    settings = Settings(daemon_port=_free_port(), state_dir=tmp_path)
    servers: list[asyncio.Server] = []

    def fake_spawn(spawn_settings: Settings) -> None:
        # Stands in for the detached process: write a token, start listening a moment later.
        async def listen_soon() -> None:
            await asyncio.sleep(0.1)
            create_token_file(
                daemon_token_file(spawn_settings.state_dir, spawn_settings.daemon_port)
            )
            servers.append(
                await asyncio.start_server(_answer_ping, "127.0.0.1", spawn_settings.daemon_port)
            )

        asyncio.get_running_loop().create_task(listen_soon())

    def must_not_spawn(spawn_settings: Settings) -> None:
        pytest.fail("a running daemon must not be started again")

    try:
        await ensure_daemon(settings, spawn=fake_spawn)
        assert len(servers) == 1
        await ensure_daemon(settings, spawn=must_not_spawn)
    finally:
        for server in servers:
            server.close()


async def _refuse_token(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    await reader.readline()
    writer.write(encode_error("missing or wrong token"))
    await writer.drain()
    writer.close()


def _must_not_spawn(spawn_settings: Settings) -> None:
    pytest.fail("a second daemon on a port that answers can never bind")


@pytest.mark.asyncio
async def test_a_port_that_refuses_our_token_fails_at_once_without_spawning(tmp_path: Path) -> None:
    settings = Settings(daemon_port=_free_port(), state_dir=tmp_path)
    create_token_file(daemon_token_file(tmp_path, settings.daemon_port))
    server = await asyncio.start_server(_refuse_token, "127.0.0.1", settings.daemon_port)

    try:
        with pytest.raises(DaemonStartError, match="stale token"):
            await ensure_daemon(settings, spawn=_must_not_spawn)
    finally:
        server.close()
