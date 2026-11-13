"""Claude Code PostToolUse hook: tell the calling agent how full its context is.

Run as `<tools/contextmeter venv>/Scripts/python.exe -I -m contextmeter.hook`.
It reads the hook's stdin JSON, measures the context of the agent that made the
tool call (a subagent's own transcript when `agent_id` is set), and prints a
`hookSpecificOutput.additionalContext` line when there's something to say.
It always exits 0 and prints nothing on failure, so it can never block or fail
a tool call; failures go to .state/errors.log.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

from contextmeter.announce import decide
from contextmeter.config import CONFIG_FILE, configured_window
from contextmeter.state import ERROR_LOG, STATE_FILE, agent_key, load_levels, save_level
from contextmeter.threshold import handoff_threshold
from contextmeter.transcript import agent_transcript, latest_usage
from contextmeter.window import context_window

# parents: [0] contextmeter, [1] src, [2] contextmeter tool, [3] tools, [4] repo root
REPO_ROOT = Path(__file__).resolve().parents[4]

MAX_ERROR_LOG_BYTES = 64 * 1024


def context_note(
    event: dict[str, Any], agents_md: Path, state_file: Path, config_file: Path
) -> str | None:
    """Return the line to inject for this tool call, or None to stay quiet.

    Raises:
        ValueError: The event lacks session_id or transcript_path, or the config
            file isn't valid TOML.
        OSError: The transcript, config or state file can't be read or written.
    """
    session_id = event.get("session_id")
    transcript_path = event.get("transcript_path")
    is_valid = isinstance(session_id, str) and isinstance(transcript_path, str)
    if not is_valid or not transcript_path:
        raise ValueError("hook input lacks session_id or transcript_path")
    agent_id = event.get("agent_id") if isinstance(event.get("agent_id"), str) else None

    usage = latest_usage(agent_transcript(transcript_path, agent_id))
    if usage is None:
        return None  # no assistant turn written yet
    used_tokens, model = usage
    window = context_window(model, used_tokens, configured_window(config_file))
    used_pct = 100 * used_tokens / window

    key = agent_key(session_id, agent_id)
    last_level = load_levels(state_file).get(key)
    level, note = decide(used_pct, handoff_threshold(agents_md), last_level or 0)
    if level != last_level:  # also records first sight of an agent, at level 0
        save_level(state_file, key, level)
    return note


def _log_error(error: BaseException) -> None:
    """Append the error's type and message (never the input) to the error log."""
    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        is_full = ERROR_LOG.exists() and ERROR_LOG.stat().st_size > MAX_ERROR_LOG_BYTES
        with ERROR_LOG.open("w" if is_full else "a", encoding="utf-8") as handle:
            handle.write(f"{type(error).__name__}: {error}\n")
    except OSError:
        pass  # nowhere left to report it, and the hook must still exit 0


def main() -> int:
    """Hook entry point. Always returns 0."""
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
        if not isinstance(event, dict):
            raise ValueError("hook input isn't a JSON object")
        project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or REPO_ROOT)
        note = context_note(event, project_dir / "AGENTS.md", STATE_FILE, CONFIG_FILE)
        if note:
            output = {"hookEventName": "PostToolUse", "additionalContext": note}
            sys.stdout.write(json.dumps({"hookSpecificOutput": output}))
    except Exception as error:  # noqa: BLE001 - a hook must never fail a tool call
        _log_error(error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
