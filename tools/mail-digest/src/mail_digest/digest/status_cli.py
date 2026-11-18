"""`mail-digest status`: the setup tool's health check, from the state file alone.

Reads .state/state.json (never writes it, never takes the run lock, never starts a
run) and prints one JSON line {words, fix, command} (tools/setup/README.md, "Verify
checks"). Exit 0 when no run has failed since the last good one, 1 otherwise.
"""

import json
from datetime import datetime
from pathlib import Path

from mail_digest.memory import load_state
from mail_digest.settings import MAX_ANNOUNCED_KEYS, STATE_PATH

EXIT_OK = 0
EXIT_FAILED = 1
RUN_NOW = "uv run --project tools/mail-digest --frozen --no-sync mail-digest --now"
LOG_NAME = "tools/mail-digest/.state/mail-digest.log"


def status_summary(state_path: Path) -> tuple[int, dict[str, str | None]]:
    """The exit code and {words, fix, command} for the state file at `state_path`.

    Every run saves the state, so the file's modified time is when the last one ended.
    """
    if not state_path.is_file():
        fix = "It runs every morning once its schedule step is done, or start one now."
        return EXIT_OK, _summary("set up, no run yet", fix, RUN_NOW)
    state = load_state(state_path, MAX_ANNOUNCED_KEYS, keep_copy=False)
    if state.was_reset:
        fix = "The next run starts fresh (it re-reads a few days of mail)."
        return EXIT_FAILED, _summary("its state file is unreadable", fix, RUN_NOW)
    ended = datetime.fromtimestamp(state_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    if state.failures:
        runs = "run" if state.failures == 1 else f"{state.failures} runs"
        fix = f"See {LOG_NAME}, then run it again."
        return EXIT_FAILED, _summary(f"the last {runs} failed ({ended})", fix, RUN_NOW)
    return EXIT_OK, _summary(f"last run worked ({ended})")


def main() -> int:
    """Print the summary line and return its exit code."""
    code, summary = status_summary(STATE_PATH)
    print(json.dumps(summary))
    return code


def _summary(words: str, fix: str | None = None, command: str | None = None) -> dict:
    """The summary object."""
    return {"words": words, "fix": fix, "command": command}
