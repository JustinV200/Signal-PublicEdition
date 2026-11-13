"""sleepmode's tunable values, plus the projector name it shares with the whiteboard.

The values are few and rarely change, so they live here (like tools/mail-digest's
settings.py). Only the per-machine lighting choices go in sleepmode.toml
(config_file.py). The projector is matched by the whiteboard's own
`[display] name_match`, so both tools always agree on which display is the projector.
"""

import logging
import tomllib
from pathlib import Path

from sleepmode.config.paths import WHITEBOARD_CONFIG

log = logging.getLogger(__name__)

# The whiteboard's default `[display] name_match` (tools/whiteboard/whiteboard.example.toml).
DEFAULT_PROJECTOR_MATCH = "PROJ-1"

# VCP 0xD6 value sent to turn a monitor off. 4 is "DPM off": the monitor still listens
# on DDC/CI, so 1 turns it back on. 5 ("power off") is deeper, but many monitors then
# need their power button, so it's not used.
DDC_OFF_VALUE = 4
# Seconds to wait after a DDC power-off before checking that the monitor stayed off.
# Some monitors see the live video signal and switch straight back on.
DDC_SETTLE_S = 2.0

# Keyboard or mouse input this soon after sleep mode starts doesn't wake it, so the
# Enter key that ran `sleepmode sleep` (or a nudge of the mouse) doesn't undo it.
INPUT_GRACE_S = 5.0

# Seconds a keeper gets to exit by itself once a wake marks the state awake (it
# normally goes within a second). One still running after that is ended.
KEEPER_EXIT_WAIT_S = 5.0
# Seconds a new keeper must stay up for sleep to count as started. One that crashes on
# start (at import, say) goes well within this, and sleep then wakes everything back up.
KEEPER_STARTUP_CHECK_S = 2.0

# The one-shot per-user scheduled task that runs `sleepmode wake` at the wake time.
WAKE_TASK_NAME = "Signal sleep mode wake"
# Task Scheduler's backstop if a wake run hangs.
WAKE_TASK_TIME_LIMIT = "PT5M"

# Lighting (sleepmode.lighting).
# Seconds one vendor command may run before it's killed.
LIGHTING_COMMAND_TIMEOUT_S = 10.0
# OpenRGB's SDK server (its defaults; it listens on loopback only).
OPENRGB_HOST = "127.0.0.1"
OPENRGB_PORT = 6742
# Where the portable OpenRGB was unpacked, under %LOCALAPPDATA%, when openrgb_path is unset.
OPENRGB_DEFAULT_PARTS = ("Programs", "OpenRGB", "OpenRGB.exe")
# Seconds to wait for a server sleepmode started to listen and finish finding devices.
OPENRGB_START_TIMEOUT_S = 20.0
# Seconds one OpenRGB.exe command-line run (saving a profile) may take; 1.2 s on this PC.
OPENRGB_CLI_TIMEOUT_S = 15.0
# Its device list grows for a moment after it starts listening; once the count holds
# this long, detection counts as done (it took about 0.5 s on this PC).
OPENRGB_SETTLE_S = 2.0
# Room on top of OpenRGB's two waits for the reconnect after a save and the device
# changes (well under a second on this PC).
_LIGHTING_STEP_SLACK_S = 10.0
# Each backend's off or restore gets this long in all, so a hung OpenRGB or vendor tool
# can't hold up sleep or wake (one that overruns is abandoned). OpenRGB's slowest
# healthy sleep starts the server and then saves a snapshot, so the deadline is built
# from both waits: a smaller one would abandon that sleep with its lights half off.
LIGHTING_STEP_TIMEOUT_S = OPENRGB_START_TIMEOUT_S + OPENRGB_CLI_TIMEOUT_S + _LIGHTING_STEP_SLACK_S
# The owner's daytime look, saved in OpenRGB's GUI; wake loads it first.
DAY_PROFILE = "day"
# What sleep saves just before the lights go off; wake loads it when there's no day profile.
SNAPSHOT_PROFILE = "sleepmode-before"


def projector_match(config_path: Path = WHITEBOARD_CONFIG) -> str:
    """The projector's name match: the whiteboard's `[display] name_match`, else the default.

    Args:
        config_path: The whiteboard's optional whiteboard.toml.

    Returns:
        A case-insensitive substring of the projector's friendly or device name.
        A missing, unreadable or invalid file falls back to DEFAULT_PROJECTOR_MATCH
        (logged unless the file is simply absent).
    """
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DEFAULT_PROJECTOR_MATCH
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        log.warning(
            "can't read %s (%s); matching the projector by %r",
            config_path,
            error,
            DEFAULT_PROJECTOR_MATCH,
        )
        return DEFAULT_PROJECTOR_MATCH
    display = data.get("display")
    match = display.get("name_match") if isinstance(display, dict) else None
    if match is None:
        return DEFAULT_PROJECTOR_MATCH
    if not isinstance(match, str):
        log.warning(
            "%s: [display] name_match isn't a string; using %r",
            config_path,
            DEFAULT_PROJECTOR_MATCH,
        )
        return DEFAULT_PROJECTOR_MATCH
    return match
