"""The one subprocess helper for the kit package (uv calls), with error context."""

from __future__ import annotations

import os
import subprocess


class KitError(RuntimeError):
    """A uv command failed while building or inspecting a venv."""


def uv_env() -> dict[str, str]:
    """This process's env without UV_CONSTRAINT.

    The lead's session carries UV_CONSTRAINT (the kit constraints) as a guard for plain
    `uv pip install`; the kit's own uv calls pass their own constraints, so it must not apply.
    """
    return {k: v for k, v in os.environ.items() if k != "UV_CONSTRAINT"}


def run_cmd(cmd: list[str]) -> str:
    """Run cmd with uv_env() as its environment and return stdout.

    Raises KitError with the command and stderr on failure.
    """
    try:
        done = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            env=uv_env(),
        )
    except OSError as exc:
        raise KitError(f"cannot run {cmd[0]}: {exc}") from exc
    if done.returncode != 0:
        raise KitError(f"{' '.join(cmd)} exited {done.returncode}: {done.stderr.strip()}")
    return done.stdout
