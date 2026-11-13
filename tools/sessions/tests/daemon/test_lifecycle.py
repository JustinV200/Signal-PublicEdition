"""Daemon lifecycle over IPC: start, send, status, stop, resume, approvals and failures."""

import asyncio
import importlib
from pathlib import Path

import pytest
from support.fakes import FakeApprover, FakeClientFactory, result

from claude_sessions.approvals import PermissionModeError
from claude_sessions.config import Settings
from claude_sessions.ipc import MAX_LINE_BYTES, DaemonRequestError

pytestmark = pytest.mark.asyncio

UNMANAGED_ID = "99999999-9999-4999-8999-999999999999"
# The module, not the serve() function the daemon package exports under the same name.
serve_module = importlib.import_module("claude_sessions.daemon.serve")


async def test_start_send_status_and_stop(daemon, repo: Path) -> None:
    started = await daemon.call("start", repo=str(repo), prompt="Reply with pong.", model="sonnet")
    session_id = started["id"]
    assert started["state"] == "working"

    status = await daemon.wait_for_state(session_id, "idle")
    assert status["last_texts"] == ["pong"]
    options = daemon.factory.clients[0].options
    assert (options.cwd, options.model, options.permission_mode) == (str(repo), "sonnet", "default")
    assert options.session_id == status["claude_session_id"]

    await daemon.call("send", id=session_id, prompt="again")
    status = await daemon.wait_for_state(session_id, "idle")
    assert status["last_texts"] == ["pong", "echo: again"]
    # The CLI's running total (0.01, then 0.02) is counted once.
    assert status["cost_usd"] == pytest.approx(0.02)

    stopped = await daemon.call("stop", id=session_id)
    assert (stopped["state"], stopped["is_live"]) == ("stopped", False)
    assert daemon.factory.clients[0].is_disconnected
    with pytest.raises(DaemonRequestError, match="isn't running; use resume"):
        await daemon.call("send", id=session_id, prompt="more")
    assert "Demo session finished: pong" in await daemon.drain_notes()


async def test_tool_approval_waits_for_the_owner_and_a_no_denies(daemon, repo: Path) -> None:
    async def ask_then_report(client, prompt: str) -> None:
        decision = await client.ask_permission(
            "Bash", {"command": "git push"}, "Claude wants to run git push"
        )
        client.emit(result(client.options.session_id, decision.behavior))

    daemon.factory.script = ask_then_report
    daemon.approver.answer = False
    daemon.approver.release.clear()

    session_id = (await daemon.call("start", repo=str(repo), prompt="push it"))["id"]
    waiting = await daemon.wait_for_state(session_id, "awaiting_permission")
    assert "git push" in waiting["pending_approval"]
    daemon.approver.release.set()

    done = await daemon.wait_for_state(session_id, "idle")
    assert done["pending_approval"] is None
    request = daemon.approver.requests[0]
    assert (request.repo_name, request.tool_name, request.session_id) == (
        "Demo",
        "Bash",
        session_id,
    )
    notes = await daemon.drain_notes()
    assert any("needs approval: Claude wants to run git push" in note for note in notes)
    assert "Demo session finished: deny" in notes
    assert [note.priority for note in daemon.hub.notes] == ["high", "normal"]


async def test_bypass_permissions_is_refused_by_client_and_daemon(daemon, repo: Path) -> None:
    with pytest.raises(PermissionModeError):
        await daemon.call("start", repo=str(repo), prompt="x", permission_mode="bypassPermissions")
    args = {"repo": str(repo), "prompt": "x", "permission_mode": "bypassPermissions"}

    [reply] = await daemon.raw(daemon.request_line("start", args))

    assert reply["ok"] is False and "never allowed" in reply["error"]
    assert daemon.factory.clients == []


async def test_requests_without_the_token_are_refused_and_the_connection_closed(
    daemon, repo: Path
) -> None:
    start = {"repo": str(repo), "prompt": "x"}
    # A web page can POST text/plain to loopback; the body arrives after the HTTP lines.
    no_token_shutdown = daemon.request_line("shutdown", {}, token=None)
    http_post = b"POST / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n" + no_token_shutdown
    valid_ping = daemon.request_line("ping", {})
    wrong_then_valid = daemon.request_line("start", start, token="guess") + valid_ping

    for line in (http_post, daemon.request_line("start", start, token=None), wrong_then_valid):
        # One error reply, then the daemon hangs up without reading the rest.
        [reply] = await daemon.raw(line)
        assert reply["ok"] is False

    assert "token" in reply["error"]
    assert daemon.factory.clients == []
    assert await daemon.call("ping")


async def test_a_second_daemon_that_cannot_bind_leaves_the_live_token_alone(daemon) -> None:
    live_token = daemon.token_file.read_text(encoding="ascii")

    with pytest.raises(OSError):
        await daemon.rival_server().start()

    assert daemon.token_file.read_text(encoding="ascii") == live_token
    assert await daemon.call("ping")


async def test_a_rival_serve_that_cannot_bind_leaves_sessions_json_alone(
    daemon, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = (await daemon.call("start", repo=str(repo), prompt="pong"))["id"]
    await daemon.wait_for_state(session_id, "idle")
    sessions_json = daemon.token_file.parent / "sessions.json"
    live_records = sessions_json.read_bytes()
    # Keep the test process out of a kill-on-close job object.
    monkeypatch.setattr(serve_module, "kill_children_with_daemon", lambda: None)
    rival = Settings(daemon_port=daemon.server.port, state_dir=daemon.token_file.parent)

    with pytest.raises(OSError):
        await serve_module.serve(rival, FakeApprover(), FakeClientFactory())

    # Loading would have marked the idle session stopped and saved over the live file.
    assert sessions_json.read_bytes() == live_records
    assert (await daemon.call("status", id=session_id))["state"] == "idle"


async def test_sessions_only_run_in_folders_inside_the_repo_roots(daemon, short_tmp: Path) -> None:
    outside = short_tmp / "Elsewhere"
    outside.mkdir()
    # Mixed slash forms too: resolving any of these would open an SMB connection.
    network_or_device = (
        r"\\server\share\repo",
        r"\\?\C:\Windows",
        r"/\host\share\x",
        r"\/host/share",
        r"/\.\C:\Windows",
        "//host/share",
    )

    with pytest.raises(DaemonRequestError, match="outside the repo roots"):
        await daemon.call("start", repo=str(outside), prompt="x")
    for folder in network_or_device:
        # This message comes only from the string pre-check, before any filesystem call.
        with pytest.raises(DaemonRequestError, match="network or device path"):
            await daemon.call("start", repo=folder, prompt="x")
    daemon.transcript_cwds[UNMANAGED_ID] = outside
    with pytest.raises(DaemonRequestError, match="outside the repo roots"):
        await daemon.call("resume", session=UNMANAGED_ID, prompt="x")

    assert daemon.factory.clients == [] and await daemon.call("list") == []


async def test_sessions_survive_a_restart_and_can_be_resumed(daemon, repo: Path) -> None:
    session_id = (await daemon.call("start", repo=str(repo), prompt="pong"))["id"]
    claude_id = (await daemon.wait_for_state(session_id, "idle"))["claude_session_id"]

    await daemon.crash_and_restart()
    [listed] = await daemon.call("list")
    assert (listed["id"], listed["state"], listed["is_live"]) == (session_id, "stopped", False)

    resumed = await daemon.call("resume", session=claude_id, prompt="where were we")
    assert resumed["id"] == session_id
    status = await daemon.wait_for_state(session_id, "idle")
    assert status["last_texts"][-1] == "echo: where were we"
    assert daemon.factory.clients[-1].options.resume == claude_id

    daemon.transcript_cwds[UNMANAGED_ID] = repo
    adopted = await daemon.call("resume", session=UNMANAGED_ID, prompt="continue")
    assert adopted["id"] != session_id and adopted["repo"] == "Demo"
    assert daemon.factory.clients[-1].options.resume == UNMANAGED_ID


async def test_two_resumes_of_one_unmanaged_session_launch_one_cli(daemon, repo: Path) -> None:
    daemon.transcript_cwds[UNMANAGED_ID] = repo

    replies = await asyncio.gather(
        daemon.call("resume", session=UNMANAGED_ID, prompt="a"),
        daemon.call("resume", session=UNMANAGED_ID, prompt="b"),
        return_exceptions=True,
    )

    refused = [r for r in replies if isinstance(r, DaemonRequestError)]
    assert len(refused) == 1 and "already running" in str(refused[0])
    assert len(daemon.factory.clients) == 1 and len(await daemon.call("list")) == 1


async def test_a_cli_that_exits_mid_session_is_an_error(daemon, repo: Path) -> None:
    async def exit_at_once(client, prompt: str) -> None:
        client.end_stream()

    daemon.factory.script = exit_at_once
    session_id = (await daemon.call("start", repo=str(repo), prompt="hi"))["id"]

    status = await daemon.wait_for_state(session_id, "error")

    assert status["is_live"] is False and "exited unexpectedly" in status["error"]
    assert await daemon.drain_notes() == [
        "Demo session hit an error: the Claude CLI exited unexpectedly"
    ]


async def test_malformed_unknown_and_oversized_requests_get_error_replies(daemon) -> None:
    [unknown] = await daemon.raw(daemon.request_line("format_disk", {}))
    assert "unknown op" in unknown["error"]
    [bad_id] = await daemon.raw(daemon.request_line("stop", {"id": "../../etc"}))
    assert "isn't a session id" in bad_id["error"]

    [oversized] = await daemon.raw(b"x" * (MAX_LINE_BYTES + 10) + b"\n")

    assert oversized["ok"] is False and "longer than" in oversized["error"]
    assert await daemon.call("ping")
