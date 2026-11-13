"""The composition root: builds SleepMode and the keeper's callbacks from the real parts.

The CLI and the MCP server call these; tests build SleepMode with fakes instead.
"""

import sys
from datetime import datetime
from functools import partial
from pathlib import Path

from signal_displays import list_monitors

from sleepmode.config import (
    CONFIG_FILE,
    DDC_OFF_VALUE,
    DDC_SETTLE_S,
    INPUT_GRACE_S,
    KEEPER_EXIT_WAIT_S,
    KEEPER_STARTUP_CHECK_S,
    STATE_DIR,
    STATE_FILE,
    TOOL_ROOT,
    WAKE_TASK_NAME,
    WAKE_TASK_TIME_LIMIT,
    WHITEBOARD_ROOT,
    WHITEBOARD_STATE_DIR,
    projector_match,
)
from sleepmode.control import SleepDeps, SleepMode, StateFileError, load_state
from sleepmode.keeper import NightView, StateReading, is_process_alive, start_keeper, stop_keeper
from sleepmode.lighting import Lighting
from sleepmode.schedule import WakeScheduler, WakeTask
from sleepmode.screens import ScreenPower, ddc
from sleepmode.whiteboard_link import NightViewClient, night_seed, start_whiteboard_if_down

# The wake task runs the venv's windowless interpreter, so nothing flashes on screen.
WAKE_TASK_ARGUMENTS = "-m sleepmode wake --reason schedule"


def build_sleep_mode() -> SleepMode:
    """SleepMode wired to the real displays, whiteboard, Task Scheduler, lights and keeper."""
    task = WakeTask(
        name=WAKE_TASK_NAME,
        command=_windowless_python(),
        arguments=WAKE_TASK_ARGUMENTS,
        working_dir=TOOL_ROOT,
        time_limit=WAKE_TASK_TIME_LIMIT,
    )
    deps = SleepDeps(
        state_path=STATE_FILE,
        list_monitors=list_monitors,
        projector_match=projector_match(),
        screens=ScreenPower(ddc=ddc, off_value=DDC_OFF_VALUE, settle_s=DDC_SETTLE_S),
        whiteboard=NightViewClient(WHITEBOARD_STATE_DIR),
        start_whiteboard=partial(start_whiteboard_if_down, WHITEBOARD_STATE_DIR, WHITEBOARD_ROOT),
        scheduler=WakeScheduler(task, STATE_DIR),
        lighting=Lighting(CONFIG_FILE),
        start_keeper=partial(start_keeper, startup_check_s=KEEPER_STARTUP_CHECK_S),
        stop_keeper=partial(stop_keeper, wait_s=KEEPER_EXIT_WAIT_S),
        is_alive=is_process_alive,
        now=datetime.now,
        grace_s=INPUT_GRACE_S,
    )
    return SleepMode(deps)


def read_state_for_keeper() -> StateReading:
    """What the keeper needs from the state file.

    Raises:
        OSError: A transient read failure (the keeper retries).
    """
    try:
        state = load_state(STATE_FILE)
    except StateFileError:
        return StateReading(is_readable=False)
    if state is None:
        return StateReading(is_readable=False)
    return StateReading(is_readable=True, is_asleep=state.is_asleep, session_id=state.session_id)


def night_view_for_keeper(sky: bool) -> NightView:
    """The keeper's whiteboard calls: is the night view up, and show it (tonight's seed)."""
    client = NightViewClient(WHITEBOARD_STATE_DIR)
    return NightView(client.is_showing, partial(client.show, night_seed(datetime.now()), sky))


def _windowless_python() -> Path:
    """pythonw.exe next to this interpreter (uv venvs have both), else this interpreter."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return pythonw if pythonw.exists() else Path(sys.executable)
