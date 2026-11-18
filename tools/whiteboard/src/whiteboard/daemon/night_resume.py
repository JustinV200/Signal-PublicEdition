"""resume_night: a daemon that starts while sleep mode is on opens on the night view.

Sleep mode shows the night view once, when it turns on. A daemon started later
in the night (a board_* call, the 06:00 sync, a restart after a crash) would
otherwise open the kiosk on the day view at full brightness. This reads
tools/sleepmode's state file (read-only) before the kiosk opens.
"""

import logging
from datetime import datetime
from pathlib import Path

from signal_jsonstate import StateFileError, read_json_object

from whiteboard.display.server import BoardController, night_seed

logger = logging.getLogger(__name__)


async def resume_night(board: BoardController, sleep_state_file: Path) -> None:
    """Show the night view if sleep mode is on and the scene isn't already on it.

    A missing or unreadable state file means awake: it's logged, never raised.

    Args:
        board: The daemon's board, before the kiosk opens.
        sleep_state_file: tools/sleepmode/.state/state.json.
    """
    if board.scene.night is not None:
        return
    try:
        # Retries through sleepmode's os.replace, which a plain read hits as PermissionError.
        state = read_json_object(sleep_state_file)
        if state.get("is_asleep") is not True:
            return
        seed = night_seed(datetime.fromisoformat(state["since"]))
    except (StateFileError, ValueError, KeyError, TypeError, AttributeError) as error:
        logger.warning("Couldn't read sleep mode's state (%s); not resuming the night view", error)
        return
    await board.show_night(seed)
    logger.info("sleep mode is on: starting on the night view (seed %d)", seed)
