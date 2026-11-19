"""Runs one setup step and returns its status.

The same code serves the terminal UI and the agent's non-interactive commands; the
difference is the `Asker` passed in. A step that needs an answer the asker doesn't
have returns NEEDS_INPUT instead of guessing.
"""

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from signal_setup import detect, progress
from signal_setup.prereqs import missing
from signal_setup.registry import Step, Tool
from signal_setup.samples import collect
from signal_setup.steps.settings_step import NEEDS_INPUT
from signal_setup.steps.settings_step import run as run_settings
from signal_setup.wiring import set_constant, set_env_value

# The argv field the console's port fills (the logon step's -Port {port}).
PORT_FIELD = "{" + progress.PORT_ANSWER + "}"


class Asker(Protocol):
    """Where a step's answers come from: the terminal, or the agent's command-line flags."""

    interactive: bool  # True at the terminal; the agent's asker has no answers to prompt for

    def say(self, text: str) -> None:
        """Show a line to the user."""

    def confirm(self, question: str, default: bool) -> bool | None:
        """Yes/no; None when there's no answer yet."""

    def text(self, question: str) -> str | None:
        """A typed value; None when there's no answer yet."""


def _fill(argv: tuple[str, ...], answers: dict[str, str], say: Callable[[str], None]) -> list[str]:
    """`argv` with {email}, {port} and other answers filled in. Raises KeyError if one is missing.

    A stored answer beats its default (progress.DEFAULT_ANSWERS). {port} is the checked
    stored port (progress.stored_port: a bad one falls back to the default, with a note
    via `say`), the same one the setup window opens on.
    """
    answers = {**progress.DEFAULT_ANSWERS, **answers}
    if any(PORT_FIELD in arg for arg in argv):
        answers[progress.PORT_ANSWER] = str(progress.stored_port(answers, say))
    return [arg.format(**answers) if "{" in arg else arg for arg in argv]


def _run(root: Path, step: Step, data: dict[str, Any], asker: Asker) -> str:
    """Run the step's command in the repo root, output going straight to the terminal."""
    lacking = missing(step.prereqs)
    if lacking:
        asker.say("Missing: " + "; ".join(f"{p.name} ({p.hint})" for p in lacking))
        return progress.FAILED
    try:
        argv = _fill(step.argv, data["answers"], asker.say)
    except KeyError as missing_answer:
        asker.say(f"Answer the {missing_answer} step first.")
        return NEEDS_INPUT
    program = shutil.which(argv[0])
    if program is None:
        asker.say(f"{argv[0]} isn't installed or isn't on PATH.")
        return progress.FAILED
    asker.say("$ " + " ".join(argv))
    # The resolved path, not the bare name: Windows only finds .exe files on its own, so
    # npm (npm.cmd) would fail to start.
    result = subprocess.run([program, *argv[1:]], cwd=root)
    return progress.DONE if result.returncode == 0 else progress.FAILED


def _copy(root: Path, step: Step, asker: Asker) -> str:
    """Copy an example file, keeping any copy the user already has."""
    dst = root / step.dst
    if dst.exists():
        asker.say(f"Kept your existing {step.dst}.")
        return progress.DONE
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / step.src, dst)
    asker.say(f"Copied {step.src} to {step.dst}.")
    return progress.DONE


def _manual(step: Step, asker: Asker) -> str:
    """Show instructions; done once the user says they did them."""
    asker.say(step.text + (f"\n(Details: {step.doc})" if step.doc else ""))
    answer = asker.confirm("Done?", True)
    return NEEDS_INPUT if answer is None else (progress.DONE if answer else progress.SKIPPED)


def _email(root: Path, step: Step, data: dict[str, Any], asker: Asker) -> str:
    """Ask the address once, then write it into each source constant the step lists."""
    address = asker.text(step.title)
    if not address:
        return NEEDS_INPUT
    try:
        for edit in step.edits:
            set_constant(root / edit["file"], edit["name"], address.strip())
    except ValueError as error:
        asker.say(str(error))
        return progress.FAILED
    data["answers"]["email"] = address.strip()
    return progress.DONE


def _env(root: Path, step: Step, asker: Asker) -> str:
    """Ask a non-secret value and save it in .env."""
    value = asker.text(step.title)
    if not value:
        return NEEDS_INPUT
    try:
        set_env_value(root, step.key, value.strip())
    except ValueError as error:
        asker.say(str(error))
        return progress.FAILED
    return progress.DONE


def run_step(root: Path, tool: Tool, step: Step, data: dict[str, Any], asker: Asker) -> str:
    """Run `step` of `tool` and record the result in `data` (unless it still needs input).

    The samples kind is terminal-only (it prompts directly); the agent uses `setup samples`.
    A tool found already set up (detect.py) is taken on with its first result: its record
    starts as the one its detection assumed, so the tool stays done.
    Returns 'done', 'skipped', 'failed' or NEEDS_INPUT.
    """
    # Read before the step runs: an install makes the very evidence detection looks for.
    found_record = detect.record_to_adopt(root, tool, data)
    if step.kind == "confirm":
        answer = asker.confirm(step.title, step.default)
        status = NEEDS_INPUT if answer is None else (progress.DONE if answer else progress.SKIPPED)
    elif step.kind == "run":
        status = _run(root, step, data, asker)
    elif step.kind == "copy":
        status = _copy(root, step, asker)
    elif step.kind == "manual":
        status = _manual(step, asker)
    elif step.kind == "email":
        status = _email(root, step, data, asker)
    elif step.kind == "settings":
        status = run_settings(
            root, tool, step, data, asker, lambda again: run_step(root, tool, again, data, asker)
        )
    elif step.kind == "samples":
        mail_ready = progress.step_status(data, "mail", "signin") == progress.DONE
        status = progress.DONE if collect(root, mail_ready) else progress.SKIPPED
    else:
        status = _env(root, step, asker)
    if status != NEEDS_INPUT:
        progress.adopt(data, tool.id, found_record)
        progress.set_step(data, tool.id, step.id, status)
    return status
