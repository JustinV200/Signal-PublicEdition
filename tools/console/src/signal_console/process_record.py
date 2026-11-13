"""Find a process again from the pid and start time a state file saved (hub.json, daemon.json).

Windows reuses pids, so each record keeps psutil's create_time beside the pid,
and only a running process whose start time matches counts as the recorded one.
"""

import math

import psutil

# create_time is a float; a match within this counts as the same start.
CREATE_TIME_TOLERANCE_S = 0.01


def find_recorded_process(pid: int, create_time: float) -> psutil.Process | None:
    """The running process with this pid and start time.

    Args:
        pid: The recorded pid.
        create_time: psutil's create_time for it, as recorded.

    Returns:
        The process, or None if it has exited or its pid now belongs to another process.
    """
    try:
        process = psutil.Process(pid)
        is_same = math.isclose(process.create_time(), create_time, abs_tol=CREATE_TIME_TOLERANCE_S)
    except psutil.Error:
        return None
    return process if is_same else None
