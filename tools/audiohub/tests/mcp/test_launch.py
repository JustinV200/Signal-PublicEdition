"""Real stdio round trip: spawn `audiohub mcp` through uv and talk JSON-RPC to it over pipes.

Runs the exact repo-root command that `.mcp.json` registers. Checks the
initialize handshake, the server name (it sets the mcp__audiohub__ prefix),
that `tools/list` names every tool, and that stdout carries nothing but
JSON-RPC (a stray print would break every client). No hub needs to be
running: only listing is exercised. It skips when uv isn't on PATH.

A static drift test, which needs no uv or subprocess, also checks that the
music pause's tool names are served tools under the `.mcp.json` server key.
"""

import json
import queue
import shutil
import subprocess
import threading
from pathlib import Path
from typing import IO, Any

import pytest

from audiohub.config import REPO_ROOT
from audiohub.loop.music_pause import AUDIOHUB_TOOL_PREFIX, PLAYBACK_TOOLS, SKIP_TOOLS
from audiohub.mcp import SERVER_NAME

# The args registered in the repo root's .mcp.example.json (setup copies it to .mcp.json;
# see the mcp package README).
MCP_JSON_ARGS = ["run", "--project", "tools/audiohub", "--frozen", "audiohub", "mcp"]
# Newest revision that still uses the initialize handshake (what Claude Code sends).
PROTOCOL_VERSION = "2025-11-25"
# Generous: the first `uv run` in a fresh checkout may still be syncing the venv.
RESPONSE_TIMEOUT_S = 90.0
EXIT_TIMEOUT_S = 30.0

EXPECTED_TOOLS = {
    "notify",
    "music_now_playing",
    "music_play",
    "music_pause",
    "music_next",
    "music_previous",
    "music_set_volume",
    "music_search_and_play",
    "music_play_liked",
    "music_queue",
}

UV = shutil.which("uv")


class StdioPeer:
    """A minimal MCP client over a subprocess's stdin/stdout, one JSON object per line.

    A thread pumps stdout lines into a queue so reads can time out instead of
    hanging the test run.
    """

    def __init__(self, command: list[str], cwd: Path, stderr: IO[bytes]) -> None:
        self.process = subprocess.Popen(
            command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr
        )
        self._lines: queue.Queue[bytes | None] = queue.Queue()
        threading.Thread(target=self._pump_stdout, daemon=True).start()

    def _pump_stdout(self) -> None:
        for line in self.process.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def send(self, message: dict[str, Any]) -> None:
        self.process.stdin.write(json.dumps(message).encode("utf-8") + b"\n")
        self.process.stdin.flush()

    def request(self, request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a request and return its response, skipping any notifications."""
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        while True:
            line = self._lines.get(timeout=RESPONSE_TIMEOUT_S)
            assert line is not None, "server closed stdout before responding"
            message = json.loads(line)  # fails on anything that isn't JSON-RPC
            if message.get("id") == request_id:
                return message

    def close(self) -> tuple[int, list[bytes]]:
        """Close stdin, wait for exit, and return the exit code and leftover stdout lines."""
        self.process.stdin.close()
        exit_code = self.process.wait(timeout=EXIT_TIMEOUT_S)
        leftover = []
        while (line := self._lines.get(timeout=EXIT_TIMEOUT_S)) is not None:
            leftover.append(line)
        return exit_code, leftover


def test_the_music_pause_names_the_served_tools() -> None:
    # The hub's music pause spots Claude's music commands by these names, so a
    # renamed tool or server key would silently stop it noticing them.
    mcp_json = json.loads((REPO_ROOT / ".mcp.example.json").read_text(encoding="utf-8"))
    assert SERVER_NAME in mcp_json["mcpServers"]
    assert f"mcp__{SERVER_NAME}__" == AUDIOHUB_TOOL_PREFIX
    assert PLAYBACK_TOOLS | SKIP_TOOLS <= EXPECTED_TOOLS


@pytest.mark.skipif(UV is None, reason="uv is not on PATH")
def test_mcp_json_command_serves_every_tool_over_stdio(tmp_path) -> None:
    with open(tmp_path / "stderr.log", "wb") as stderr:
        peer = StdioPeer([UV, *MCP_JSON_ARGS], REPO_ROOT, stderr)
        try:
            names, server_name = _list_tools(peer)
            exit_code, leftover = peer.close()
        finally:
            if peer.process.poll() is None:
                peer.process.kill()
    log = (tmp_path / "stderr.log").read_text(encoding="utf-8", errors="replace")
    assert server_name == "audiohub", log
    assert names == EXPECTED_TOOLS, log
    assert exit_code == 0, log
    for line in leftover:
        json.loads(line)


def _list_tools(peer: StdioPeer) -> tuple[set[str], str]:
    """Run initialize + initialized + tools/list; return the tool names and server name."""
    initialize = peer.request(
        1,
        "initialize",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "audiohub-tests", "version": "0"},
        },
    )
    peer.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    listed = peer.request(2, "tools/list", {})
    names = {tool["name"] for tool in listed["result"]["tools"]}
    return names, initialize["result"]["serverInfo"]["name"]
