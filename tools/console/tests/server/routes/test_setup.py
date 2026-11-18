"""POST /api/setup/run: fixed CLI argv only, live NDJSON lines and the exit code, one at a time.

The fixture's runner runs tests/fakes/fake_setup_cli.py, which echoes its argv and stdin.
"""

import json

import pytest

from signal_console.setup_cli import terminal_command


async def _run(console, body):
    response = await console.client.post(
        "/api/setup/run", json=body, headers=console.page_headers()
    )
    if response.status != 200:
        return response.status, []
    return 200, [json.loads(line) for line in (await response.text()).splitlines()]


@pytest.mark.parametrize(
    ("body", "args", "stdin", "exit_code"),
    [
        ({"command": "status"}, ["status", "--json"], None, 0),
        (
            {"command": "choose", "tools": ["mail", "calendar"]},
            ["choose", "mail,calendar"],
            None,
            0,
        ),
        ({"command": "auto", "tools": ["mail", "brief"]}, ["auto", "mail,brief"], None, 0),
        (
            {"command": "apply", "tool": "mail", "step": "email", "value": "exit=3"},
            ["apply", "mail", "email", "--value=exit=3"],
            None,
            3,
        ),
        (
            {"command": "config", "tool": "jobhunt", "set": {"Applications per run": "5"}},
            ["config", "jobhunt", "--set=Applications per run=5"],
            None,
            0,
        ),
        (
            {"command": "samples", "action": "paste", "kind": "email", "text": "hi there"},
            ["samples", "paste", "--kind=email"],
            "hi there",
            0,
        ),
    ],
)
async def test_run_streams_the_fixed_command(console, body, args, stdin, exit_code):
    status, records = await _run(console, body)

    assert status == 200
    lines = [r["line"] for r in records if "line" in r]
    assert lines[0] == "args " + json.dumps(args)
    assert (f"stdin {stdin}" in lines) == (stdin is not None)
    assert records[-1] == {"exit": exit_code}


@pytest.mark.parametrize(
    "body",
    [
        {"command": "rm"},
        {"command": ["list"]},
        # verify's rows carry a failing check's raw output: not for the page.
        {"command": "verify", "tools": ["mail"]},
        {"command": "apply", "tool": "--help", "step": "x"},
        {"command": "apply", "tool": "mail", "step": "email", "value": "a\nb"},
        {"command": "apply", "tool": "mail", "step": "email", "value": "a\x9bb"},
        {"command": "apply", "tool": "mail", "step": "email", "answer": "maybe"},
        {"command": "mark", "tool": "mail", "step": "signin", "status": "failed"},
        # doc takes ids only: never a path or a flag.
        {"command": "doc", "tool": "vault", "step": "../../AGENTS.md"},
        {"command": "doc", "tool": "-x", "step": "add"},
        {"command": "doc", "tool": "vault"},
        {"command": "config", "tool": "mail", "set": {"-x": "1"}},
        {"command": "config", "tool": "mail", "set": {"a=b": "1"}},
        {"command": "samples", "action": "files", "paths": ["--kind=code"]},
        {"command": "samples", "action": "keep", "numbers": [1, True]},
        {"command": "samples", "action": "paste", "text": "x" * 60_001},
    ],
)
async def test_run_refuses_anything_else(console, body):
    assert (await _run(console, body))[0] == 400


async def test_writes_run_one_at_a_time_and_reads_beside_them(console, monkeypatch):
    write = {"command": "mark", "tool": "mail", "step": "signin", "status": "done"}
    runner = console.services.setup
    await runner._lock.acquire()  # a write in flight
    try:
        assert (await _run(console, write))[0] == 409
        assert (await _run(console, {"command": "list"}))[0] == 200
        # Lost the race after the route's own check: the stream says busy, not just failed.
        real_check, checks = runner.check_free, []

        def free_once_then_busy():
            checks.append(1)
            if len(checks) > 1:
                real_check()

        monkeypatch.setattr(runner, "check_free", free_once_then_busy)
        status, records = await _run(console, write)
        assert status == 200 and records[0]["busy"] is True and records[-1] == {"exit": 1}
    finally:
        runner._lock.release()
    monkeypatch.undo()
    assert (await _run(console, write))[0] == 200


async def test_setup_routes_need_the_page_token(console):
    response = await console.client.post(
        "/api/setup/run", json={"command": "list"}, headers={"Origin": console.origin}
    )
    assert response.status == 401


def test_terminal_runs_only_setup_ps1_step_for_a_tool_and_step(tmp_path):
    assert terminal_command(tmp_path, "vault", "init")[-4:] == [
        str(tmp_path / "setup.ps1"),
        "step",
        "vault",
        "init",
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"tool": "vault; calc", "step": "init"},
        {"tool": "vault"},
        {"tool": "vault", "step": "--help"},
        {"tool": "vault", "step": "init; calc"},
        {"tool": "vault", "step": "init\n"},
        {"tool": "vault", "step": ["init"]},
    ],
)
async def test_terminal_refuses_an_unchecked_id(console, body):
    # Refused before anything starts, so no window opens here.
    response = await console.client.post(
        "/api/setup/terminal", json=body, headers=console.page_headers()
    )
    assert response.status == 400
