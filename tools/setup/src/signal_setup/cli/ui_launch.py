"""`setup ui [tool]` (and a bare `setup`): open the setup wizard in the Signal console window.

The wizard lives in the console's web app, so this first checks the programs it needs
(one line each), installs and builds the console with its own registry steps (recorded in
progress like any other step, shown as "1/3 Installing" and so on), then runs
`console open --view setup --port <port>`. A `--port` is stored first as the `port` answer,
which the console's logon step registers on; without one the stored port (else 8790) is
used, so a second checkout set up on 8791 stays there. When any of that can't work (not
Windows, a missing program, a failed build, a console that didn't open) it says why in
one line (for the last, who holds the port, cli/port_holder.py) and falls back to the
terminal setup, or, without a terminal to prompt in (the setup skill's shell), exits 1
so the skill carries on in chat.
"""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from signal_setup import platforms, progress, registry
from signal_setup.cli.port_holder import port_holder_words
from signal_setup.prereqs import PREREQS
from signal_setup.registry import Tool
from signal_setup.steps import run_step
from signal_setup.terminal import TerminalAsker
from signal_setup.ui import run_setup

CONSOLE_ID = "console"
# The console steps the window needs, in order, each with the word shown as it starts
# ("1/3 Installing"). web-build also re-runs when dist is gone.
BOOTSTRAP_STEPS = (("install", "Installing"), ("web-deps", "Packages"), ("web-build", "Building"))
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


def _check_programs(console: Tool) -> list[str]:
    """Print one line per program the window needs: found, or missing and how to get it.

    Returns the names of the missing ones (empty when all are there).
    """
    lacking = []
    for prereq in (PREREQS[name] for name in console.prereqs):
        if prereq.is_present():
            print(f"Checking {prereq.name}: found")
            continue
        print(f"Checking {prereq.name}: missing, {prereq.how_to_get()}")
        lacking.append(prereq.name)
    return lacking


def _bootstrap(root: Path) -> str:
    """Install and build the console. Returns '' when ready, else why it can't open."""
    if platforms.current() != platforms.WINDOWS:
        return "The setup window needs Windows (the console is Windows-only)."
    console = registry.by_id(CONSOLE_ID)
    lacking = _check_programs(console)
    if lacking:
        return f"The setup window needs {', '.join(lacking)} (see above)."
    data, asker = progress.load(root), TerminalAsker()
    for number, (step_id, word) in enumerate(BOOTSTRAP_STEPS, 1):
        if not _needs_run(root, data, step_id):
            continue
        step = console.step(step_id)
        print(f"{number}/{len(BOOTSTRAP_STEPS)} {word}")
        status = run_step(root, console, step, data, asker)
        progress.save(root, data)
        if status != progress.DONE:
            return f"Couldn't prepare the setup window ({step.title} failed)."
    return ""


def _fallback(
    root: Path, why: str, terminal_setup: Callable[..., None], tool_id: str | None = None
) -> int:
    """Say why, then run the terminal setup, or exit 1 when there's no terminal to prompt in."""
    print(why)
    if not sys.stdin.isatty():
        print("No terminal to prompt in: carry on in chat, or run `setup --no-ui` yourself.")
        return 1
    print("Carrying on in the terminal instead.")
    terminal_setup(root, tool_id)
    return 0


def _console_port(root: Path, port: int | None) -> int:
    """The console's port: `port` when given, else the stored answer, else the default.

    A given port is stored as the `port` answer, which the logon step's {port} uses.
    """
    data = progress.load(root)
    if port is None:
        return progress.stored_port(data["answers"], print)
    data["answers"][progress.PORT_ANSWER] = str(port)
    progress.save(root, data)
    return port


def _open_failure(root: Path, port: int) -> str:
    """Why the window didn't open, in one line: who holds the port, when someone else does."""
    holder = port_holder_words(port, root)
    if holder is None:
        return "The setup window couldn't open: console open failed (its reason is above)."
    return (
        f"The setup window couldn't open: port {port} is used by {holder}. "
        r"Close it, or run .\setup.cmd --port <a free port>."
    )


def launch(
    root: Path,
    tool_id: str | None = None,
    port: int | None = None,
    terminal_setup: Callable[..., None] = run_setup,
) -> int:
    """Open the wizard (at `tool_id`'s steps when given). Returns the exit code.

    Args:
        root: The repo root.
        tool_id: A registry tool id to open the wizard at, or None for where it left off.
        port: The console's port, stored as the `port` answer; None keeps the stored one
            (8790 when none is). A console server this starts listens on it (a running one
            keeps its own).
        terminal_setup: The fallback flow (the interactive setup; tests pass a fake).
    """
    if tool_id is not None:
        registry.by_id(tool_id)  # KeyError for an unknown id, before anything is installed
    port = _console_port(root, port)
    why = _bootstrap(root)
    if why:
        return _fallback(root, why, terminal_setup, tool_id)
    command = [*OPEN_COMMAND, "--port", str(port), *(["--tool", tool_id] if tool_id else [])]
    if subprocess.run(command, cwd=root).returncode != 0:
        return _fallback(root, _open_failure(root, port), terminal_setup, tool_id)
    print("The setup window is open. Progress saves as you go; close it any time.")
    return 0
