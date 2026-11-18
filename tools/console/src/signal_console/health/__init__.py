"""Public API of signal_console.health: the console's own checks, as rows.

`console doctor` prints them and the token-guarded `GET /api/health` sends
them. Every check only reads local files and process tables, so it works
with the server down and never sends a key or token anywhere.
"""

from signal_console.health.inputs import HealthPaths
from signal_console.health.report import health_rows
from signal_console.health.row import ATTENTION, FAIL, OK, SETUP_COMMAND, HealthRow, Level
from signal_console.health.server_check import port_row

__all__ = [
    "ATTENTION",
    "FAIL",
    "OK",
    "SETUP_COMMAND",
    "HealthPaths",
    "HealthRow",
    "Level",
    "health_rows",
    "port_row",
]
