"""Finds the Claude Code CLI and runs one hidden, timed, init-checked claude process.

On this PC the CLI ships inside the VS Code extension and isn't on PATH, and the
extension's folder name changes with every update, so the newest one is found at
run time. claude prints stream-json: the `init` event is checked (init_check.py)
before the model acts, and the final `result` event is returned for result.py.
"""

import functools
import json
import os
import shutil
import subprocess
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from mail_digest.child_env import CREATE_NO_WINDOW, clean_env, kill_tree
from mail_digest.claude.init_check import init_problems
from mail_digest.claude.lockdown import DIGEST_LOCKDOWN, Lockdown

VSCODE_EXTENSIONS_DIR = Path.home() / ".vscode" / "extensions"
EXTENSION_GLOB = "anthropic.claude-code-*"
EXTENSION_BINARY = Path("resources") / "native-binary" / "claude.exe"
# How long claude gets to exit by itself (shutting its MCP servers down) once its
# output ends, before its tree is killed.
EXIT_GRACE_S = 10


class ClaudeNotFoundError(RuntimeError):
    """No Claude Code CLI on PATH or in the VS Code extensions folder."""


@dataclass(frozen=True)
class LaunchOptions:
    """Where and how long claude runs, where its stderr goes (overwritten per run), and
    the lockdown its init event is checked against."""

    cwd: Path
    timeout_s: int
    stderr_path: Path
    lockdown: Lockdown = DIGEST_LOCKDOWN


@dataclass(frozen=True)
class ClaudeRun:
    """What one claude process produced.

    result: the final stream-json `result` event, or None if there wasn't one.
    error: why the run didn't finish normally ("" if it did).
    version: claude_code_version from the init event ("" if none was seen).
    """

    result: dict | None = None
    error: str = ""
    version: str = ""


def find_claude(
    which: Callable[[str], str | None] = shutil.which,
    extensions_dir: Path = VSCODE_EXTENSIONS_DIR,
) -> Path:
    """`claude.exe` on PATH, else the newest VS Code extension's bundled binary.

    Only an .exe counts: an npm `claude.cmd` shim would run through cmd.exe, which
    re-parses the arguments (the JSON schema's quotes included).
    Raises ClaudeNotFoundError if neither exists.
    """
    on_path = which("claude.exe")
    if on_path:
        return Path(on_path)
    binaries = [d / EXTENSION_BINARY for d in extensions_dir.glob(EXTENSION_GLOB)]
    binaries = [b for b in binaries if b.is_file()]
    if not binaries:
        raise ClaudeNotFoundError(f"no claude on PATH or under {extensions_dir}")
    return max(binaries, key=lambda b: _version_key(b.parents[2].name))


def run_claude(argv: list[str], stdin_text: str, options: LaunchOptions) -> ClaudeRun:
    """Run claude to completion, killing it on a bad init event or after options.timeout_s.

    Every kill takes claude's whole process tree (its MCP servers too): at the
    timeout, on a bad init event, and when claude is still running EXIT_GRACE_S
    after its output ends (the timer is off by then).

    Raises OSError if it can't start or the stderr file can't be opened.
    """
    options.stderr_path.parent.mkdir(parents=True, exist_ok=True)
    with options.stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=options.cwd,
            env=clean_env(os.environ),
            creationflags=CREATE_NO_WINDOW,
        )
        timed_out = threading.Event()
        kill = functools.partial(kill_tree, "claude", process)
        timer = threading.Timer(options.timeout_s, _kill, (kill, timed_out))
        timer.daemon = True
        timer.start()
        try:
            _send(process, stdin_text)
            run = read_events(process.stdout, kill, options.cwd, options.lockdown)
        finally:
            timer.cancel()
            # Without the kill, a claude that closed its output but kept running would
            # be waited on forever: the timeout no longer applies.
            try:
                exit_code = process.wait(EXIT_GRACE_S)
            except subprocess.TimeoutExpired:
                kill()
                exit_code = process.wait()
    if timed_out.is_set():
        error = f"claude ran past {options.timeout_s} s and was killed"
        return ClaudeRun(error=error, version=run.version)
    if run.error or run.result is not None:
        return run
    return ClaudeRun(error=f"claude exited {exit_code} with no result", version=run.version)


def read_events(
    lines: Iterable[str],
    kill: Callable[[], None],
    cwd: Path,
    lockdown: Lockdown = DIGEST_LOCKDOWN,
) -> ClaudeRun:
    """Read claude's stream-json lines; call kill and stop on a bad or missing init.

    cwd is the folder claude was started in, which the init event must report, and
    lockdown the tools and servers it must list (init_check.py).
    Other events (the model's turns, with email text in them) are skipped, never logged.
    """
    version, saw_init, result = "", False, None
    for line in lines:
        event = _parse_event(line)
        if event.get("type") == "system" and event.get("subtype") == "init":
            saw_init, version = True, str(event.get("claude_code_version", ""))
            problems = init_problems(event, cwd, lockdown)
            if problems:
                kill()
                error = "lockdown check failed: " + "; ".join(problems)
                return ClaudeRun(error=error, version=version)
        elif event.get("type") == "result":
            result = event
    if result is not None and not saw_init:
        return ClaudeRun(error="no init event, so the lockdown wasn't checked")
    return ClaudeRun(result=result, version=version)


def _send(process: subprocess.Popen, text: str) -> None:
    """Write the run context to claude's stdin and close it."""
    try:
        process.stdin.write(text)
        process.stdin.close()
    except OSError:
        pass  # claude already exited; read_events reports the missing result.


def _kill(kill: Callable[[], None], timed_out: threading.Event) -> None:
    """Timer callback: mark the run as timed out, then kill (claude's whole process tree).

    Killing only claude would leave its MCP servers running, and one that holds
    claude's stdout keeps read_events waiting for output that never comes.
    """
    timed_out.set()
    kill()


def _parse_event(line: str) -> dict:
    """One stream-json line as a dict ({} for anything that isn't a JSON object)."""
    # A line nested deeper than the recursion limit raises RecursionError. The model
    # writes some lines (its tool calls), so an email could steer it into one.
    try:
        event = json.loads(line)
    except (ValueError, RecursionError):
        return {}
    return event if isinstance(event, dict) else {}


def _version_key(folder_name: str) -> tuple[int, ...]:
    """(2, 1, 301) from "anthropic.claude-code-2.1.301-win32-x64"; () if unparsable."""
    version = folder_name.removeprefix("anthropic.claude-code-").split("-")[0]
    parts = version.split(".")
    return tuple(int(p) for p in parts) if all(p.isdigit() for p in parts) else ()
