"""Keep the PC awake with SetThreadExecutionState, without touching the power plan.

ES_CONTINUOUS ties the request to the calling thread until it's cleared or the
process exits, so the keeper's main thread holds it all night. Windows drops it
by itself if the keeper dies, so nothing can leave the PC stuck awake.
"""

import ctypes
import logging

log = logging.getLogger(__name__)

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


def hold_awake(keep_display_on: bool) -> None:
    """Stop Windows from sleeping (and from blanking the displays, if asked) on this thread.

    Args:
        keep_display_on: Also keep the displays on, so the projector's night sky
            isn't cut off by the display timeout.

    Raises:
        OSError: Windows refused the request.
    """
    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    _set_state(flags | ES_DISPLAY_REQUIRED if keep_display_on else flags)
    log.info("holding the PC awake (display too: %s)", keep_display_on)


def release_awake() -> None:
    """Clear this thread's request; Windows' normal sleep and display timeouts apply again."""
    try:
        _set_state(ES_CONTINUOUS)
    except OSError as error:
        # The process is about to exit, which clears the request anyway.
        log.warning("couldn't release the keep-awake request: %s", error)


def _set_state(flags: int) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.SetThreadExecutionState.restype = ctypes.c_uint32
    kernel32.SetThreadExecutionState.argtypes = [ctypes.c_uint32]
    if kernel32.SetThreadExecutionState(flags) == 0:
        raise ctypes.WinError(ctypes.get_last_error())
