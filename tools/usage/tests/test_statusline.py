"""Tests for the status line entry point: it always prints a line and exits 0."""

import io
import json
import sys
from datetime import timedelta

import pytest

from usage import statusline
from usage.store import StateLockTimeoutError
from usage.times import local_now, to_iso


@pytest.mark.parametrize(
    ("raw_input", "expected_line"),
    [
        (b"", statusline.MINIMAL_LINE),
        (
            b'{"rate_limits":{"five_hour":{"used_percentage":42.4,"resets_at":4000000000}}}',
            "5h 42% · wk -- · 0 agents",
        ),
        (b"[1, 2]", "5h -- · wk -- · 0 agents"),
        (
            b'{"rate_limits": {"five_hour": "x", "seven_day": '
            b'{"used_percentage": NaN, "resets_at": 1e300}}}',
            "5h -- · wk -- · 0 agents",
        ),
    ],
)
def test_garbage_stdin_still_prints_a_line_and_exits_zero(
    raw_input, expected_line, tmp_path, monkeypatch, capsysbinary
):
    monkeypatch.setattr(statusline, "STATE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(statusline, "ERROR_LOG", tmp_path / "errors.log")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw_input)))

    assert statusline.main() == 0
    assert capsysbinary.readouterr().out.decode("utf-8") == f"{expected_line}\n"


SESSION_INPUT = (
    b'{"session_id": "s1", "rate_limits": '
    b'{"five_hour": {"used_percentage": 42, "resets_at": 4000000000}}}'
)


def _write_two_sessions(state_file, now):
    agent = {"type": "Explore", "seen_at": to_iso(now)}
    sessions = {
        "s1": {"agents": [{**agent, "id": "a1"}, {**agent, "id": "a2"}]},
        "s2": {"agents": [{**agent, "id": "a3"}]},
    }
    state_file.write_text(json.dumps({"sessions": sessions}), encoding="utf-8")


def test_busy_lock_still_prints_known_numbers_and_own_agent_count(tmp_path, monkeypatch):
    def busy(*args, **kwargs):
        raise StateLockTimeoutError("held")

    monkeypatch.setattr(statusline, "update_state", busy)
    monkeypatch.setattr(statusline, "ERROR_LOG", tmp_path / "errors.log")
    now = local_now()
    state_file = tmp_path / "usage.json"
    _write_two_sessions(state_file, now)

    line = statusline.render_status_line(SESSION_INPUT, state_file, now)
    assert line == "5h 42% · wk -- · 2 agents (3 all)"


def test_repeated_input_does_not_rewrite_the_file(tmp_path):
    state_file = tmp_path / "usage.json"
    now = local_now()
    statusline.render_status_line(SESSION_INPUT, state_file, now)
    written, mtime = state_file.read_bytes(), state_file.stat().st_mtime_ns

    # An idle session re-sends the same values 30 s later: nothing changes, changed_at included.
    statusline.render_status_line(SESSION_INPUT, state_file, now + timedelta(seconds=30))
    assert state_file.read_bytes() == written
    assert state_file.stat().st_mtime_ns == mtime
