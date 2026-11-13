"""Writes fake Claude Code transcripts (JSONL) into a fake CLAUDE_CONFIG_DIR for the tests.

The layout and record shapes match what the CLI writes: one folder per
working directory under projects/, named by replacing every non-alphanumeric
character of the path with "-", holding one <session id>.jsonl per session.
"""

import json
import os
import re
from pathlib import Path

_NON_ALPHANUMERIC = re.compile(r"[^a-zA-Z0-9]")


def write_transcript(
    config_dir: Path, cwd: Path, session_id: str, prompt: str, mtime: float | None = None
) -> Path:
    """Write a two-record transcript (user prompt, assistant reply) and return its path."""
    project_dir = config_dir / "projects" / _NON_ALPHANUMERIC.sub("-", str(cwd))
    project_dir.mkdir(parents=True, exist_ok=True)
    common = {"sessionId": session_id, "cwd": str(cwd), "timestamp": "2026-10-19T12:00:00.000Z"}
    records = [
        {
            **common,
            "type": "user",
            "uuid": "u1",
            "parentUuid": None,
            "message": {"role": "user", "content": prompt},
        },
        {
            **common,
            "type": "assistant",
            "uuid": "a1",
            "parentUuid": "u1",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
        },
    ]
    path = project_dir / f"{session_id}.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path
