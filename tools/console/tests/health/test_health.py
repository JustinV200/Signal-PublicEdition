"""The console's health rows, from fake state and settings files in a temp folder.

Never the real .state or settings: every path comes from tmp_health_paths.
"""

import json
from datetime import datetime, timedelta

import pytest
from conftest import tmp_health_paths
from signal_orchestrator import Claim, claim_to_json
from signal_orchestrator.testing import fake_inbox, unused_pipe_address

from signal_console.health import ATTENTION, FAIL, OK, HealthRow, health_rows, server_check
from signal_console.health.port_holder import PortHolder, project_from_paths

NOW = datetime(2026, 11, 17, 12, 0).astimezone()
TURN = "signal_console.hooks.turn"
SESSION = "signal_console.hooks.session"


def _row(rows: list[HealthRow], row_id: str) -> HealthRow:
    return next(row for row in rows if row.id == row_id)


def _hooks(*entries: tuple[str, str]) -> dict:
    # Settings holding one hook group per (event, module), shaped as setup's `wire` writes them.
    hooks: dict = {}
    for event, module in entries:
        command = {"type": "command", "command": "python.exe", "args": ["-m", module]}
        hooks.setdefault(event, []).append({"hooks": [command]})
    return {"hooks": hooks}


TURN_ALL = [(e, TURN) for e in ("UserPromptSubmit", "Stop", "StopFailure", "Notification")]
SESSION_ALL = [(e, SESSION) for e in ("SessionStart", "PostModelSwitch")]


@pytest.mark.parametrize(
    ("case", "reply_after_claim", "report"),
    [
        ("linked", timedelta(minutes=5), OK),
        # a reply from before this claim proves nothing about this session's hook
        ("closed", timedelta(minutes=-5), ATTENTION),
        # no claim: any reply on record counts
        ("none", timedelta(minutes=-5), OK),
        # no reply at all
        ("unreadable", None, ATTENTION),
    ],
)
async def test_claim_and_last_report_rows(tmp_path, case, reply_after_claim, report):
    paths = tmp_health_paths(tmp_path)
    claimed_at = NOW - timedelta(hours=1)
    if reply_after_claim is not None:
        reply = {"role": "claude", "at": (claimed_at + reply_after_claim).isoformat()}
        (tmp_path / "history.jsonl").write_text(json.dumps({"event": "message", "data": reply}))
    async with fake_inbox() as inbox:
        socket = inbox.address if case == "linked" else unused_pipe_address()
        if case in ("linked", "closed"):
            claim = Claim(socket, "tok", "main", claimed_at.isoformat())
            (tmp_path / "orchestrator.json").write_text(json.dumps(claim_to_json(claim)))
        elif case == "unreadable":
            (tmp_path / "orchestrator.json").write_text("{not json")

        rows = health_rows(paths, NOW)

    row = _row(rows, "claim")
    assert row.level == (OK if case == "linked" else ATTENTION)
    assert row.state == case
    if case != "linked":
        assert "console claim" in (row.command or "")
    assert _row(rows, "hook-report").level == report


@pytest.mark.parametrize(
    ("project", "local", "expected"),
    [
        # complete, in the local file only
        ({}, _hooks(*TURN_ALL, *SESSION_ALL), (OK, OK, OK)),
        # partial: Stop and the whole session hook missing
        ({}, _hooks(*[t for t in TURN_ALL if t[0] != "Stop"]), (FAIL, FAIL, OK)),
        # split across the two files: still installed, each once
        (_hooks(*TURN_ALL), _hooks(*SESSION_ALL), (OK, OK, OK)),
        # the turn hook in both files fires twice
        (_hooks(*TURN_ALL), _hooks(*TURN_ALL, *SESSION_ALL), (OK, OK, ATTENTION)),
    ],
)
def test_hook_rows_read_both_settings_files(tmp_path, project, local, expected):
    (tmp_path / "settings.json").write_text(json.dumps(project))
    (tmp_path / "settings.local.json").write_text(json.dumps(local))

    rows = health_rows(tmp_health_paths(tmp_path), NOW)

    levels = tuple(_row(rows, i).level for i in ("turn-hook", "session-hook", "hooks-twice"))
    assert levels == expected


def test_hook_errors_older_than_a_day_are_history(tmp_path):
    old = (NOW - timedelta(days=28)).replace(tzinfo=None).isoformat(timespec="seconds")
    (tmp_path / "hook.log").write_text(f"{old} <HTTPError 403: 'Forbidden'>\n" * 11)
    assert _row(health_rows(tmp_health_paths(tmp_path), NOW), "hook-errors").level == OK

    recent = (NOW - timedelta(hours=1)).replace(tzinfo=None).isoformat(timespec="seconds")
    with (tmp_path / "hook.log").open("a") as log:
        log.write(f"{recent} ValueError('bad input')\n")
    row = _row(health_rows(tmp_health_paths(tmp_path), NOW), "hook-errors")
    assert (row.level, row.fix is not None) == (ATTENTION, True)


@pytest.mark.parametrize(
    ("program", "process_paths", "named"),
    [
        # uv's venv launcher: the base python listens, the checkout shows in its command line
        (
            "python.exe",
            [r"C:\Python312\python.exe", r"D:\Other\Signal\tools\console\.venv\Scripts\python.exe"],
            r"the console of another checkout, D:\Other\Signal",
        ),
        # nothing readable without elevation: only "another program"
        ("", [], "Another program holds port 1"),
    ],
)
def test_port_held_by_another_checkout_names_it_and_the_fix(
    tmp_path, monkeypatch, program, process_paths, named
):
    holder = PortHolder(4242, program, project_from_paths(process_paths))
    monkeypatch.setattr(server_check, "find_port_holder", lambda port: holder)

    row = _row(health_rows(tmp_health_paths(tmp_path), NOW), "port")

    assert row.level == ATTENTION
    assert named in row.words
    assert row.fix is not None and "--port <a free port>" in row.fix
    assert row.command is None


async def test_health_route_returns_rows_without_secrets(console):
    socket = unused_pipe_address()
    claim = Claim(socket, "inbox-token-secret", "main", NOW.isoformat())
    (console.state_dir / "orchestrator.json").write_text(json.dumps(claim_to_json(claim)))
    (console.state_dir / "local-key").write_text(console.services.local_key)

    signed_out = await console.client.get("/api/health")
    response = await console.client.get("/api/health", headers=console.page_headers())

    assert signed_out.status == 401
    body = await response.text()
    rows = json.loads(body)["rows"]
    assert {"server", "port", "claim", "turn-hook", "hub-log"} <= {row["id"] for row in rows}
    assert all(row["fix"] for row in rows if row["level"] != OK)
    secrets = ["inbox-token-secret", socket, console.services.local_key, console.token]
    assert not [secret for secret in secrets if secret in body or json.dumps(secret)[1:-1] in body]
