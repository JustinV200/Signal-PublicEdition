"""Tests for the SubagentStart / SubagentStop hook's per-session agent sets."""

import io
import json
import sys
from datetime import timedelta

from usage import hook
from usage.agents import STALE_AGENT_AGE
from usage.hook import record_hook_event
from usage.store import read_state
from usage.times import local_now


def _event(name, session_id, agent_id):
    payload = {"hook_event_name": name, "session_id": session_id, "agent_id": agent_id}
    return json.dumps({**payload, "agent_type": "Explore"}).encode()


def test_start_stop_duplicate_start_and_prune(tmp_path):
    state_file = tmp_path / "usage.json"
    now = local_now()
    for name, agent_id in [
        ("SubagentStart", "a1"),
        ("SubagentStart", "a1"),  # resumed: still one agent
        ("SubagentStart", "a2"),
        ("SubagentStop", "a2"),
        ("SubagentStop", "never-started"),  # an internal agent's stop
    ]:
        record_hook_event(_event(name, "s1", agent_id), state_file, now)
    state = read_state(state_file)
    assert [agent["id"] for agent in state["sessions"]["s1"]["agents"]] == ["a1"]
    assert state["active_subagents"] == 1

    # a1's stop never came; once it's stale it's pruned and s1 is dropped.
    later = now + STALE_AGENT_AGE + timedelta(minutes=1)
    record_hook_event(_event("SubagentStart", "s2", "b1"), state_file, later)
    state = read_state(state_file)
    assert list(state["sessions"]) == ["s2"]
    assert state["active_subagents"] == 1

    # b1 is under the cutoff, so a later event keeps it.
    record_hook_event(_event("SubagentStart", "s2", "b2"), state_file, later + timedelta(hours=1))
    assert read_state(state_file)["active_subagents"] == 2


def test_stop_with_a_huge_bad_byte_message_still_removes_the_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "STATE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(hook, "ERROR_LOG", tmp_path / "errors.log")
    record_hook_event(_event("SubagentStart", "s1", "a1"), hook.STATE_FILE, local_now())
    # SubagentStop also carries last_assistant_message: here 2 MiB with a stray non-UTF-8 byte.
    message = b"x" * (2 * 1024 * 1024) + b"\xff"
    stop = _event("SubagentStop", "s1", "a1")[:-1] + b', "last_assistant_message": "'
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(stop + message + b'"}')))

    assert hook.main() == 0
    assert read_state(hook.STATE_FILE)["active_subagents"] == 0
