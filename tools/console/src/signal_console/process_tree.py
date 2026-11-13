"""Kill a process and only the descendants that are its own, leaving detached daemons alone.

Shared by the voice hub's stop (hub/process.py) and the whiteboard CLI's
timeout (actions/whiteboard_cli.py). A plain recursive children() would also
reach daemons a process started on purpose to outlive it (the whiteboard
daemon, the sessions daemon), so the walk only enters children the caller
says are its own.
"""

import contextlib
from collections.abc import Callable

import psutil

KILL_WAIT_S = 5.0


def owned_tree(
    root: psutil.Process, is_owned: Callable[[psutil.Process], bool]
) -> list[psutil.Process]:
    """root plus its descendants for which is_owned holds, reached only through such processes.

    Args:
        root: The top process (always included).
        is_owned: Whether a child is part of root's own tree; a child that isn't
            is skipped along with everything under it.

    Raises:
        psutil.NoSuchProcess: root has exited.
    """
    owned = [root]
    unvisited = [root]
    while unvisited:
        parent = unvisited.pop()
        try:
            children = [child for child in parent.children() if is_owned(child)]
        except psutil.NoSuchProcess:
            if parent is root:
                raise
            continue  # It exited during the walk.
        owned += children
        unvisited += children
    return owned


def kill_processes(processes: list[psutil.Process], wait_s: float = KILL_WAIT_S) -> list[int]:
    """Kill every process and wait for them to go.

    Args:
        processes: From owned_tree.
        wait_s: How long to wait for them to exit.

    Returns:
        The pids still running afterwards (empty when all are gone).

    Raises:
        psutil.Error: A kill was refused (e.g. access denied).
    """
    for process in processes:
        # A member may exit by itself while the tree is being killed.
        with contextlib.suppress(psutil.NoSuchProcess):
            process.kill()
    _, alive = psutil.wait_procs(processes, timeout=wait_s)
    return [process.pid for process in alive]
