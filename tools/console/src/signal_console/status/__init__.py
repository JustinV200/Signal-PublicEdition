"""Public API of signal_console.status: read-only views of the hub, the whiteboard and devices."""

from signal_console.status.boards import BoardStatus, read_board_status
from signal_console.status.devices import DeviceReader
from signal_console.status.hub_log import HubLine, parse_hub_line
from signal_console.status.log_tail import LogTail
from signal_console.status.voice import is_hub_listening
from signal_console.status.whiteboard_api import WhiteboardTarget, find_whiteboard

__all__ = [
    "BoardStatus",
    "DeviceReader",
    "HubLine",
    "LogTail",
    "WhiteboardTarget",
    "find_whiteboard",
    "is_hub_listening",
    "parse_hub_line",
    "read_board_status",
]
