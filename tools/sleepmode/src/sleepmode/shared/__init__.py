"""Public API of sleepmode.shared: helpers more than one sleepmode package uses."""

from sleepmode.shared.detached import popen_detached
from sleepmode.shared.processes import is_process_alive, process_creation_time

__all__ = ["is_process_alive", "popen_detached", "process_creation_time"]
