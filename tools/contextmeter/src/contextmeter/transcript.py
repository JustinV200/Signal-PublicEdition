"""Find an agent's transcript and read how many tokens its context held on the last turn.

Claude Code writes each session's transcript to `<project dir>/<session id>.jsonl`
and each subagent's to `<project dir>/<session id>/subagents/agent-<agent id>.jsonl`.
A hook firing inside a subagent gets the session's `transcript_path` plus the
subagent's `agent_id`, so the subagent's own file is derived from those two.
"""

import json
from pathlib import Path

# Transcripts grow to tens of MB, so only the tail is read. One assistant line
# can be large (it carries the tool inputs), so retry once with a bigger tail.
TAIL_SIZES_BYTES = (256 * 1024, 4 * 1024 * 1024)

USAGE_FIELDS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def agent_transcript(transcript_path: str, agent_id: str | None) -> Path:
    """Return the transcript of the agent that made the call.

    Args:
        transcript_path: The hook input's `transcript_path` (the session's file).
        agent_id: The hook input's `agent_id`, set only inside a subagent.

    Returns:
        The subagent's own transcript when `agent_id` is set (searched under
        `subagents/` if not at the usual spot), else `transcript_path`.
    """
    session_file = Path(transcript_path)
    if not agent_id or session_file.name == f"agent-{agent_id}.jsonl":
        return session_file
    # <dir>/<session>.jsonl -> <dir>/<session>/subagents/agent-<id>.jsonl
    session_dir = session_file.with_suffix("")
    direct = session_dir / "subagents" / f"agent-{agent_id}.jsonl"
    if direct.exists():
        return direct
    # Workflow agents nest deeper: subagents/workflows/<workflow id>/agent-<id>.jsonl
    nested = next(session_dir.glob(f"subagents/**/agent-{agent_id}.jsonl"), None)
    return nested or direct


def latest_usage(transcript: Path) -> tuple[int, str] | None:
    """Return (context tokens, model id) from the newest assistant message with usage.

    Context tokens = input + cache read + cache creation tokens of that request,
    i.e. everything the model was sent. Returns None if no such message is found.

    Raises:
        OSError: The transcript can't be read.
    """
    size = transcript.stat().st_size
    for tail_bytes in TAIL_SIZES_BYTES:
        with transcript.open("rb") as handle:
            handle.seek(max(0, size - tail_bytes))
            lines = handle.read().splitlines()
        if size > tail_bytes:
            lines = lines[1:]  # the first line is probably cut in half
        found = _newest_usage(lines)
        if found or size <= tail_bytes:
            return found
    return None


def _newest_usage(lines: list[bytes]) -> tuple[int, str] | None:
    """Scan `lines` newest first for an assistant entry with non-zero usage."""
    for line in reversed(lines):
        if b'"assistant"' not in line:
            continue  # cheap pre-filter before parsing JSON
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message") if isinstance(entry, dict) else None
        if entry.get("type") != "assistant" or not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        tokens = sum(int(usage.get(field) or 0) for field in USAGE_FIELDS)
        if tokens > 0:  # synthetic messages (errors, interrupts) carry zero usage
            return tokens, str(message.get("model") or "")
    return None
