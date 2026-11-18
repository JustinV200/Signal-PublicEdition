"""A voice start is done only once the hub listens; a hub that dies first fails with its log."""

import os
from pathlib import Path

import pytest

from signal_console.actions import StepFailed
from signal_console.actions.plans import HubStep
from signal_console.actions.steps import ActionTools, run_step
from signal_console.hub import HubRecord
from signal_console.hub import process as hub_process
from signal_console.paths import HUB_LOG_FILE

# A long last line is capped at 200 characters: 199 of it, then an ellipsis. A long
# run of separators once made the path pattern take ~19 s (quadratic backtracking).
LONG_LINE = "\\" * 40_000
# A made-up home folder, so the test doesn't depend on the machine.
HOME = r"C:\Users\someuser"
# Paths that shrink a lot, then one whose middle folder is a name, which once
# straddled an 800-character pre-cut and showed `'First La` with no ellipsis.
CUT_PAD = "x" * 79
CUT_LINE = (
    f"OSError: {CUT_PAD} "
    + r"'C:\data\projects\longfoldername\anotherfolder\f.bin' " * 13
    + r"'D:\backup\First Last\x.bin'"
)
CUT_SHOWN = f"(OSError: {CUT_PAD} " + "'f.bin' " * 13 + "'x.bin')."


@pytest.mark.parametrize(
    ("last_line", "shown"),
    [
        ("RuntimeError: CUDA failed", "(RuntimeError: CUDA failed). Try Start voice again."),
        # A quoted local path is cut to its last part, spaces and repr-doubled backslashes too.
        (
            r"FileNotFoundError: No such file: 'C:\\Users\\First Last\\models\\big.bin'",
            "(FileNotFoundError: No such file: 'big.bin'). Try Start voice again.",
        ),
        # The home folder alone shows as ~.
        (
            r"PermissionError: [Errno 13] Permission denied: 'C:\\Users\\someuser'",
            "(PermissionError: [Errno 13] Permission denied: '~').",
        ),
        # ...also before punctuation and with mixed separators.
        (r"OSError: (c:\users/SOMEUSER), in C:\Users\someuser.", "(OSError: (~), in ~.)."),
        ("OSError: /home/owner/hub/config.toml is empty", "(OSError: config.toml is empty)."),
        pytest.param(LONG_LINE, f"({LONG_LINE[:199]}…).", id="long-line"),
        pytest.param(CUT_LINE, CUT_SHOWN, id="cut-inside-path"),
    ],
)
async def test_a_hub_that_exits_while_starting_fails_with_its_last_log_line(
    tmp_path, monkeypatch, last_line, shown
):
    async def never_listening():
        return False

    monkeypatch.setattr(hub_process, "is_hub_listening", never_listening)
    monkeypatch.setattr(Path, "home", lambda: Path(HOME))
    (tmp_path / HUB_LOG_FILE).write_text(
        f"Traceback (most recent call last):\n  ...\n{last_line}\n\n", encoding="utf-8"
    )
    # Our own pid with the wrong start time: the recorded process is gone.
    tools = ActionTools(start_hub=lambda state_dir: HubRecord(os.getpid(), 0.0))

    with pytest.raises(StepFailed) as failure:
        await run_step(HubStep(start=True), tmp_path, tools)
    message = str(failure.value)
    assert shown in message and not any(
        name in message.lower() for name in ("owner", "first", "some")
    )
