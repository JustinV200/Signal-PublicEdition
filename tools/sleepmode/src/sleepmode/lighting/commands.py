"""CommandBackend: the owner's vendor commands from sleepmode.toml, run at sleep and at wake.

The plug-in point for lights no other backend reaches, like a vendor CLI or a
Chroma SDK script. Each command is an argv list run with no shell, no window and a
timeout. A command that fails or overruns is a note, and the rest still run, unless
Lighting abandoned the step (its overall deadline passed).
"""

import logging
import subprocess
from collections.abc import Callable, Sequence

from sleepmode.config import LIGHTING_COMMAND_TIMEOUT_S
from sleepmode.lighting.backend import LightingReport
from sleepmode.lighting.step_guard import StepGuard

log = logging.getLogger(__name__)

# run(argv, timeout_s); raises OSError or subprocess.SubprocessError on failure.
RunCommand = Callable[[Sequence[str], float], None]
Commands = tuple[tuple[str, ...], ...]


def run_command(argv: Sequence[str], timeout_s: float) -> None:
    """Run one command to completion with no shell and no window.

    Raises:
        OSError: It couldn't be started (not found, say).
        subprocess.TimeoutExpired: It ran longer than timeout_s (it's killed).
        subprocess.CalledProcessError: It exited non-zero.
    """
    # No pipes: after a timeout kill, run() would wait on them for as long as any
    # grandchild that inherited them stays up.
    subprocess.run(
        list(argv),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=timeout_s,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


class CommandBackend:
    """Runs [lighting] off_commands at sleep and restore_commands at wake."""

    name = "vendor commands"

    def __init__(
        self, off_commands: Commands, restore_commands: Commands, run: RunCommand = run_command
    ) -> None:
        """Args: the two command lists (argv tuples) and the runner (fakes in tests)."""
        self._off_commands = off_commands
        self._restore_commands = restore_commands
        self._run = run

    def off(self, may_snapshot: bool, guard: StepGuard) -> LightingReport:
        """Run every off command (may_snapshot doesn't apply); stop once guard is abandoned."""
        return self._run_all(self._off_commands, "off_commands", guard)

    def restore(self, guard: StepGuard) -> LightingReport:
        """Run every restore command; stop once guard is abandoned."""
        return self._run_all(self._restore_commands, "restore_commands", guard)

    def _run_all(self, commands: Commands, key: str, guard: StepGuard) -> LightingReport:
        if not commands:
            log.info("lighting: no [lighting] %s in sleepmode.toml; skipping", key)
            return LightingReport()
        notes: list[str] = []
        ran = 0
        for argv in commands:
            if guard.is_abandoned:
                # Lighting gave up on this step; a later wake may already have run its own.
                log.warning("lighting: %s abandoned at its deadline; not running the rest", key)
                break
            try:
                self._run(argv, LIGHTING_COMMAND_TIMEOUT_S)
            except (OSError, subprocess.SubprocessError) as error:
                log.warning("lighting: %s failed: %s", argv[0], error)
                notes.append(f"The lighting command {argv[0]} failed: {error}")
                continue
            ran += 1
            log.info("lighting: ran %s", argv[0])
        return LightingReport((f"Ran {ran} of {len(commands)} lighting commands",), tuple(notes))
