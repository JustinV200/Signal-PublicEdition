"""The setup tool's health check for the hook: `python -I -m contextmeter.check`.

Reads files only, never runs the hook or writes anything. Prints one JSON line
{words, fix, command} (tools/setup/README.md, "Verify checks") and exits 0: if this
module imports, so does the hook. The words say the threshold it will use and whether
it has run yet (it records every agent it sees in the levels file).
"""

import json
import os
import sys
from pathlib import Path

from contextmeter.hook import REPO_ROOT
from contextmeter.state import ERROR_LOG, STATE_FILE
from contextmeter.threshold import handoff_threshold

# The log as the repo root sees it, for the fix words (tools/contextmeter/.state/errors.log).
ERROR_LOG_NAME = ERROR_LOG.relative_to(REPO_ROOT).as_posix()
NOT_RUN_FIX = "It runs after each tool call once Claude Code restarts with the hook added."


def summary(agents_md: Path, state_file: Path, error_log: Path) -> dict[str, str | None]:
    """The check's {words, fix, command} from the files the hook reads and writes.

    Args:
        agents_md: AGENTS.md, where the handoff threshold is read from.
        state_file: The levels file; it exists once the hook has run.
        error_log: The hook's error log; it exists once a run failed.

    Returns:
        The summary object; command is always None (nothing to run).
    """
    has_run = state_file.is_file()
    words = f"ready, hands off at {handoff_threshold(agents_md)}%; "
    words += "has run" if has_run else "hasn't run yet"
    fix = None if has_run else NOT_RUN_FIX
    # The hook never fails a tool call, so this file is the only sign a run went wrong.
    # It's kept until the owner deletes it (the hook only cuts it back past 64 KiB).
    if error_log.is_file() and error_log.stat().st_size:
        fix = f"It logged errors: see {ERROR_LOG_NAME}, and delete it once fixed."
    return {"words": words, "fix": fix, "command": None}


def main() -> int:
    """Print the summary line. Always returns 0."""
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or REPO_ROOT)
    print(json.dumps(summary(project_dir / "AGENTS.md", STATE_FILE, ERROR_LOG)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
