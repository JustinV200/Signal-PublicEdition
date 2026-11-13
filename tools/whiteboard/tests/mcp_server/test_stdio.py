"""Real stdio round trip: spawn `whiteboard mcp` through uv and talk JSON-RPC to it over pipes.

Runs the exact repo-root command `.mcp.json` registers. Checks the initialize
handshake, the server name (it sets the mcp__whiteboard__ prefix the board
agent auto-allows), that tools/list names every tool, and that stdout carries
only JSON-RPC. Listing tools never contacts the daemon, so none needs to run.
(Mirrors tools/audiohub's test; the projects don't share test code.)
"""

import json
import queue
import shutil
import subprocess
import threading
from typing import Any

import pytest

from whiteboard.config import REPO_ROOT

MCP_JSON_ARGS = ["run", "--project", "tools/whiteboard", "--frozen", "whiteboard", "mcp"]
PROTOCOL_VERSION = "2025-11-25"
# Generous: the first `uv run` in a fresh checkout may still be syncing the venv.
RESPONSE_TIMEOUT_S = 90.0
EXIT_TIMEOUT_S = 30.0
EXPECTED_TOOLS = {
    "board_look",
    "board_draw",
    "board_move",
    "board_remove",
    "board_clear",
    "board_list",
    "board_highlight",
    "board_placeholder",
    "board_calibrate",
    "board_fit",
    "board_realign",
    "board_save",
    "board_load",
    "board_saves",
    "board_delete_save",
    "board_todo_show",
    "board_todo_hide",
    "board_todo_sync",
    "board_todo_done",
    "board_todo_undone",
    "board_tasks_show",
    "board_night_show",
    "board_night_hide",
    "board_idle_show",
    "board_idle_hide",
}

UV = shutil.which("uv")
pytestmark = pytest.mark.skipif(UV is None, reason="uv is not on PATH")


def test_mcp_json_command_lists_every_tool_over_stdio(tmp_path) -> None:
    stderr_path = tmp_path / "stderr.log"
    with open(stderr_path, "wb") as stderr:
        process = subprocess.Popen(
            [UV, *MCP_JSON_ARGS],
            cwd=REPO_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
        )
        lines = _pump_lines(process)
        try:
            initialize = _request(process, lines, 1, "initialize", _initialize_params())
            _send(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            listed = _request(process, lines, 2, "tools/list", {})
            process.stdin.close()
            exit_code = process.wait(timeout=EXIT_TIMEOUT_S)
        finally:
            if process.poll() is None:
                process.kill()
    log = stderr_path.read_text(encoding="utf-8", errors="replace")
    assert initialize["result"]["serverInfo"]["name"] == "whiteboard", log
    assert {tool["name"] for tool in listed["result"]["tools"]} == EXPECTED_TOOLS, log
    assert exit_code == 0, log
    while (line := lines.get(timeout=EXIT_TIMEOUT_S)) is not None:
        json.loads(line)  # anything left on stdout must still be JSON-RPC


def _initialize_params() -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "whiteboard-tests", "version": "0"},
    }


def _pump_lines(process: subprocess.Popen) -> "queue.Queue[bytes | None]":
    """Copy stdout lines into a queue from a thread, so reads can time out."""
    lines: queue.Queue[bytes | None] = queue.Queue()

    def pump() -> None:
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()
    return lines


def _send(process: subprocess.Popen, message: dict[str, Any]) -> None:
    process.stdin.write(json.dumps(message).encode("utf-8") + b"\n")
    process.stdin.flush()


def _request(
    process: subprocess.Popen,
    lines: "queue.Queue[bytes | None]",
    request_id: int,
    method: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Send a request and return its response, skipping notifications."""
    _send(process, {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
    while True:
        line = lines.get(timeout=RESPONSE_TIMEOUT_S)
        assert line is not None, "server closed stdout before responding"
        message = json.loads(line)
        if message.get("id") == request_id:
            return message
