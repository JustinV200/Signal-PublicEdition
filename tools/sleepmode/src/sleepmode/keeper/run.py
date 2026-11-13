"""run_keeper: the background process that holds sleep mode up all night.

While it runs it keeps the PC awake, shows the black windows, keeps the projector
dark (night_guard: the night view, retried if the whiteboard isn't up, else a black
window), and watches for two things: real keyboard or mouse use (which wakes
everything up; media keys don't count, see input_watch), and the state file (a wake
from anywhere else marks it awake, and the keeper then just exits). If the keeper
itself fails, it wakes everything rather than leave the screens dark.
It never imports sleepmode.control or whiteboard_link: the state reader, the wake
action and the night view come in as callbacks, so the dependency points one way.
"""

import logging
import time
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass

from sleepmode.config import ConfigError, InputSettings, load_input_settings
from sleepmode.keeper.awake import hold_awake, release_awake
from sleepmode.keeper.blackout import BlackoutWindows
from sleepmode.keeper.input_watch import InputWatch
from sleepmode.keeper.message_loop import pump_messages, wait_for_messages
from sleepmode.keeper.night_guard import NightGuard, NightView
from sleepmode.keeper.spawn import KeeperOptions

log = logging.getLogger(__name__)

TICK_S = 0.25
STATE_POLL_S = 1.0

# decide()'s answers.
KEEP = "keep"
EXIT = "exit"  # sleep mode ended elsewhere, or a newer sleep replaced this keeper
WAKE_ON_INPUT = "wake-on-input"
WAKE_LOST_STATE = "wake-lost-state"  # the state file is gone or corrupt: restore everything
# Not from decide(): the keep-awake, the windows or the input watch failed.
KEEPER_ERROR = "keeper-error"


@dataclass(frozen=True)
class StateReading:
    """What the keeper read from the state file.

    Attributes:
        is_readable: False when the file is missing or malformed.
        is_asleep: The file says sleep mode is on.
        session_id: The sleep the file describes.
    """

    is_readable: bool
    is_asleep: bool = False
    session_id: str = ""


ReadState = Callable[[], StateReading]
# wake(reason, only_session): only_session None means "wake whatever the state says".
Wake = Callable[[str, str | None], object]


def decide(reading: StateReading | None, session_id: str, has_input: bool) -> str:
    """Choose the keeper's next step.

    Args:
        reading: The state file's contents, or None after a transient read error.
        session_id: The sleep this keeper was started for.
        has_input: The owner pressed a key (not a media key) or used the mouse.

    Returns:
        KEEP, EXIT, WAKE_ON_INPUT or WAKE_LOST_STATE.
    """
    if reading is not None:
        if not reading.is_readable:
            return WAKE_LOST_STATE
        if not reading.is_asleep or reading.session_id != session_id:
            return EXIT
    return WAKE_ON_INPUT if has_input else KEEP


def run_keeper(
    options: KeeperOptions, read_state: ReadState, wake: Wake, night: NightView | None = None
) -> str:
    """Hold sleep mode until it ends, then release everything.

    Args:
        options: The sleep's session id, black-window rects and keep-awake flags.
        read_state: Reads the state file; raises OSError on a transient failure.
        wake: Runs the full wake (sleepmode.control.SleepMode.wake).
        night: The whiteboard's night view, kept on options.projector; None skips it.

    Returns:
        Why it stopped: one of decide's answers other than KEEP, or KEEPER_ERROR.
    """
    try:
        action = _hold_until_done(options, read_state, night)
    except Exception:
        # Whatever broke, a keeper that just exits could leave the screens dark all night.
        log.exception("keeper for %s failed; waking everything", options.session_id)
        action = KEEPER_ERROR
    # The black windows are already gone, so input gets an instant response; now the rest.
    if action == WAKE_ON_INPUT:
        wake("input", options.session_id)
    elif action == WAKE_LOST_STATE:
        wake("state file missing or corrupt", None)
    elif action == KEEPER_ERROR:
        wake("keeper error", options.session_id)
    log.info("keeper for %s stopped: %s", options.session_id, action)
    return action


def _hold_until_done(options: KeeperOptions, read_state: ReadState, night: NightView | None) -> str:
    """Hold the PC awake, the windows up and the input watched until decide says stop.

    All of them are released (in reverse) before it returns or raises.
    """
    with ExitStack() as release:
        hold_awake(options.keep_display_on)
        release.callback(release_awake)
        # The guard before the windows, so they close first: its close may wait on a check.
        guard = None
        if options.projector is not None and night is not None:
            guard = NightGuard(options.projector, night)
            release.callback(guard.close)
        windows = BlackoutWindows(options.rects)
        release.callback(windows.close)
        watch = InputWatch(options.grace_s, _input_settings())
        release.callback(watch.close)
        return _hold(options, watch, read_state, guard)


def _hold(
    options: KeeperOptions, watch: InputWatch, read_state: ReadState, guard: NightGuard | None
) -> str:
    """Pump messages and watch input and the state file until decide says to stop."""
    next_state_check = time.monotonic()
    while True:
        pump_messages()  # the black windows' messages and the input hooks' calls
        if guard is not None:
            guard.poll()
        has_input = watch.has_new_input()
        if has_input or time.monotonic() >= next_state_check:
            next_state_check = time.monotonic() + STATE_POLL_S
            action = decide(_read(read_state), options.session_id, has_input)
            if action != KEEP:
                return action
        # Not time.sleep: a hook call must run at once, or Windows drops the hook.
        wait_for_messages(TICK_S)


def _input_settings() -> InputSettings:
    """sleepmode.toml's [input], read once per keeper (so an edit applies from the next sleep)."""
    try:
        return load_input_settings()
    except ConfigError as error:
        # A typo mustn't stop the keeper: the defaults still ignore jitter.
        log.warning("%s; using the default mouse thresholds", error)
        return InputSettings()


def _read(read_state: ReadState) -> StateReading | None:
    try:
        return read_state()
    except OSError as error:
        # e.g. a sharing violation while a wake replaces the file; try again next poll.
        log.debug("state file busy: %s", error)
        return None
