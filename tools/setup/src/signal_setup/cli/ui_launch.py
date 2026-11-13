"""`setup ui [tool]` (and a bare `setup`): open the setup wizard in the Signal console window.

The wizard lives in the console's web app, so this first installs and builds the console
with its own registry steps (recorded in progress like any other step), then runs
`console open --view setup`. When any of that can't work (not Windows, a missing program,
a failed build) it falls back to the terminal setup, or, without a terminal to prompt in
(the setup skill's shell), exits 1 so the skill carries on in chat.
"""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from signal_setup import platforms, progress, registry
from signal_setup.prereqs import missing
from signal_setup.steps import run_step
from signal_setup.terminal import TerminalAsker
from signal_setup.ui import run_setup

CONSOLE_ID = "console"
# The console steps the window needs, in order. web-build also re-runs when dist is gone.
BOOTSTRAP_STEPS = ("install", "web-deps", "web-build")
DIST_INDEX = Path("tools/console/web/dist/index.html")
OPEN_COMMAND = (
    "uv", "run", "--project", "tools/console", "--frozen", "--no-sync",
    "console", "open", "--view", "setup",
)  # fmt: skip


def _needs_run(root: Path, data: dict, step_id: str) -> bool:
    """True when a bootstrap step isn't done yet (or its build output is missing)."""
    if progress.step_status(data, CONSOLE_ID, step_id) != progress.DONE:
        return True
    return step_id == "web-build" and not (root / DIST_INDEX).is_file()


def _bootstrap(root: Path) -> str:
    """Install and build the console. Returns '' when ready, else why it can't open."""
    if platforms.current() != platforms.WINDOWS:
        return "The setup window needs Windows (the console is Windows-only)."
    console = registry.by_id(CONSOLE_ID)
    lacking = missing(console.prereqs)
    if lacking:
        return "The setup window needs " + ", ".join(f"{p.name} ({p.hint})" for p in lacking)
    data, asker = progress.load(root), TerminalAsker()
    for step_id in BOOTSTRAP_STEPS:
        if not _needs_run(root, data, step_id):
            continue
        step = console.step(step_id)
        print(f"Preparing the setup window: {step.title}")
        status = run_step(root, console, step, data, asker)
        progress.save(root, data)
        if status != progress.DONE:
            return f"Couldn't prepare the setup window ({step.title} failed)."
    return ""


def _fallback(root: Path, why: str, terminal_setup: Callable[[Path], None]) -> int:
    """Say why, then run the terminal setup, or exit 1 when there's no terminal to prompt in."""
    print(why)
    if not sys.stdin.isatty():
        print("No terminal to prompt in: carry on in chat, or run `setup --no-ui` yourself.")
        return 1
    print("Carrying on in the terminal instead.")
    terminal_setup(root)
    return 0


def launch(
    root: Path,
    tool_id: str | None = None,
    terminal_setup: Callable[[Path], None] = run_setup,
    opener: Callable[[list[str], Path], int] | None = None,
) -> int:
    """Open the wizard (at `tool_id`'s steps when given). Returns the exit code.

    Args:
        root: The repo root.
        tool_id: A registry tool id to open the wizard at, or None for where it left off.
        terminal_setup: The fallback flow (the interactive setup; tests pass a fake).
        opener: Runs the open command and returns its exit code (tests pass a fake).
    """
    if tool_id is not None:
        registry.by_id(tool_id)  # KeyError for an unknown id, before anything is installed
    why = _bootstrap(root)
    if why:
        return _fallback(root, why, terminal_setup)
    command = [*OPEN_COMMAND, *(["--tool", tool_id] if tool_id else [])]
    run = opener or (lambda argv, cwd: subprocess.run(argv, cwd=cwd).returncode)
    if run(command, root) != 0:
        return _fallback(root, "The console didn't open.", terminal_setup)
    print("The setup window is open. Progress saves as you go; close it any time.")
    return 0
