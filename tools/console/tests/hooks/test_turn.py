"""The turn hook: only the claimed session reports, each event as its phase.

Both hooks (turn and session) never print and always exit 0.
"""

import asyncio
import io
import json
import sys

import psutil
import pytest

from signal_console.hooks import session, turn
from signal_console.hooks.reply import CUT_NOTE
from signal_console.hooks.turn import report_turn
from signal_console.orchestrator import SOCKET_ENV, Claim, write_claim
from signal_console.paths import DAEMON_FILE, LOCAL_KEY_FILE
from signal_console.state_files import write_json, write_secret

CLAIMED_SOCKET = r"\\.\pipe\LOCAL\cc-msg-claimed"
AT = 1_000.0
EVENTS = {
    "UserPromptSubmit": {"prompt": "hi"},
    "Stop": {
        "last_assistant_message": "All done.",
        "background_tasks": [{}, {}],
        "effort": {"level": "high"},
    },
    "StopFailure": {"error": "overloaded"},
    "Notification": {"notification_type": "idle_prompt"},
}


def _hook_input(event, **extra):
    return json.dumps({"hook_event_name": event, "session_id": "s1", **EVENTS[event], **extra})


def _claim_and_record_server(console):
    state_dir = console.state_dir
    write_claim(state_dir, Claim(CLAIMED_SOCKET, "tok", None, ""))
    # The test server runs in this process, so this process is the recorded server.
    me = psutil.Process()
    daemon = {"pid": me.pid, "createTime": me.create_time(), "port": console.client.port}
    write_json(state_dir / DAEMON_FILE, daemon)
    write_secret(state_dir / LOCAL_KEY_FILE, console.services.local_key)


async def _run_hook(console, socket, hook_input):
    queue = console.services.events.subscribe()
    # The hook is synchronous (urllib); run it beside the test server's loop.
    posted = await asyncio.to_thread(
        report_turn, hook_input.encode(), {SOCKET_ENV: socket}, console.state_dir, AT
    )
    events = [queue.get_nowait() for _ in range(queue.qsize())]
    return posted, [data["text"] for name, data in events if name == "message"]


@pytest.mark.parametrize(
    ("event", "socket", "expected"),
    [
        ("UserPromptSubmit", CLAIMED_SOCKET, ("start", None, None, [])),
        ("Stop", CLAIMED_SOCKET, ("end", 2, "high", ["All done."])),
        ("StopFailure", CLAIMED_SOCKET, ("end", None, None, [])),
        ("Notification", CLAIMED_SOCKET, ("idle", None, None, [])),
        ("Stop", r"\\.\pipe\LOCAL\cc-msg-other", None),
    ],
)
async def test_claimed_session_reports_each_event_as_its_phase(console, event, socket, expected):
    _claim_and_record_server(console)

    posted, messages = await _run_hook(console, socket, _hook_input(event))

    assert posted is (expected is not None)
    reports = [
        (r.phase, r.background_tasks, r.effort, messages) for r in console.status.turn_reports
    ]
    assert reports == ([expected] if expected else [])
    if expected:
        assert console.status.turn_reports[0].at == AT


async def test_long_reply_is_cut_to_fit_the_servers_body_limit(console):
    _claim_and_record_server(console)
    # Emoji take 4 bytes, and a quote, newline or control character grows when JSON-escaped.
    reply = '\U0001f600\U0001f600\U0001f600"\n\x01' * 6_000

    posted, [text] = await _run_hook(
        console, CLAIMED_SOCKET, _hook_input("Stop", last_assistant_message=reply)
    )

    assert posted
    assert text.endswith(CUT_NOTE)
    assert reply.startswith(text.removesuffix(CUT_NOTE))


SESSION_START = json.dumps(
    {"hook_event_name": "SessionStart", "session_id": "s1", "model": "claude-opus-5-5"}
)
HOOK_CASES = [
    *((turn, hook_input) for hook_input in ["not json", *map(_hook_input, EVENTS)]),
    (session, "not json"),
    (session, '{"hook_event_name": "SessionStart", "session_id": 5, "model": []}'),
    (session, SESSION_START),
]


@pytest.mark.parametrize(("hook", "hook_input"), HOOK_CASES)
def test_hooks_never_print_and_exit_0_on_bad_input_or_no_server(
    tmp_path, monkeypatch, capsys, hook, hook_input
):
    # Claimed, but no console server has ever started here.
    write_claim(tmp_path, Claim(CLAIMED_SOCKET, "tok", None, ""))
    monkeypatch.setattr(hook, "STATE_DIR", tmp_path)
    monkeypatch.setenv(SOCKET_ENV, CLAIMED_SOCKET)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(hook_input.encode())))

    assert hook.main() == 0
    assert capsys.readouterr().out == ""
