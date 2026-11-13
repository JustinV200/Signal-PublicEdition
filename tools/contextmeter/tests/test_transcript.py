"""Tests for finding an agent's transcript and reading its latest usage."""

import json

from contextmeter.transcript import agent_transcript, latest_usage


def _assistant(model, input_tokens, cache_read, cache_creation):
    usage = {
        "input_tokens": input_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation,
        "output_tokens": 999,
    }
    return {"type": "assistant", "message": {"model": model, "usage": usage}}


def test_reads_newest_usage_from_subagent_transcript(tmp_path):
    session_file = tmp_path / "s1.jsonl"
    session_file.write_text("{}\n", encoding="utf-8")
    agent_file = agent_transcript(str(session_file), "abc")
    assert agent_file == tmp_path / "s1" / "subagents" / "agent-abc.jsonl"

    agent_file.parent.mkdir(parents=True)
    lines = [
        _assistant("claude-opus-5-5", 5, 1000, 10),
        {"type": "user", "message": {"content": "hi"}},
        _assistant("claude-opus-5-5", 2, 60000, 500),
        _assistant("<synthetic>", 0, 0, 0),  # zero usage is skipped
        "not json",
    ]
    text = "\n".join(line if isinstance(line, str) else json.dumps(line) for line in lines)
    agent_file.write_text(text, encoding="utf-8")
    assert latest_usage(agent_file) == (60502, "claude-opus-5-5")

    # Workflow agents' transcripts sit deeper, under subagents/workflows/<id>/.
    workflow_file = tmp_path / "s1" / "subagents" / "workflows" / "wf1" / "agent-xyz.jsonl"
    workflow_file.parent.mkdir(parents=True)
    workflow_file.write_text("", encoding="utf-8")
    assert agent_transcript(str(session_file), "xyz") == workflow_file
