"""Tests for the hook end to end: output shape and never failing."""

import io
import json
import sys

import pytest

from contextmeter import hook


def _run(monkeypatch, tmp_path, stdin_bytes):
    monkeypatch.setattr(hook, "STATE_FILE", tmp_path / "levels.json")
    monkeypatch.setattr(hook, "ERROR_LOG", tmp_path / "errors.log")
    monkeypatch.setattr(hook, "CONFIG_FILE", tmp_path / "contextmeter.toml")  # missing: table
    monkeypatch.delenv("CONTEXTMETER_WINDOW_TOKENS", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(stdin_bytes)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert hook.main() == 0
    return out.getvalue()


def test_injects_usage_for_the_main_agent(monkeypatch, tmp_path):
    transcript = tmp_path / "s1.jsonl"
    usage = {"input_tokens": 1, "cache_read_input_tokens": 116_000}
    entry = {"type": "assistant", "message": {"model": "claude-haiku-5-5", "usage": usage}}
    transcript.write_text(json.dumps(entry), encoding="utf-8")
    event = {"session_id": "s1", "transcript_path": str(transcript)}

    output = json.loads(_run(monkeypatch, tmp_path, json.dumps(event).encode()))
    context = output["hookSpecificOutput"]["additionalContext"]
    assert context == "Context: 58% used (handoff at 75%)."
    # Same band on the next call: quiet.
    assert _run(monkeypatch, tmp_path, json.dumps(event).encode()) == ""


@pytest.mark.parametrize(
    "stdin_bytes",
    [
        b"",
        b"\xff\xfe garbage",
        b"[1, 2]",
        b'{"session_id": "s1"}',
        b'{"session_id": "s1", "transcript_path": "/no/such/file.jsonl", "agent_id": 5}',
    ],
)
def test_never_fails_or_prints_on_bad_input(monkeypatch, tmp_path, stdin_bytes):
    assert _run(monkeypatch, tmp_path, stdin_bytes) == ""
    assert (tmp_path / "errors.log").exists()
