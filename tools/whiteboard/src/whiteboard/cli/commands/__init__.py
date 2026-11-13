"""The registry of `whiteboard` subcommands, in the order `whiteboard --help` lists them.

Each module defines its Command records; heavy imports (daemon, MCP SDK,
OpenCV) happen inside run(), so starting any command stays quick.
"""

from whiteboard.cli.commands.alignment import ALIGN, CALIBRATE, FIT, REALIGN
from whiteboard.cli.commands.board import CLEAR, DRAW, LOOK
from whiteboard.cli.commands.camera import CAMERA
from whiteboard.cli.commands.hardware import CAMERAS, DISPLAYS
from whiteboard.cli.commands.mcp import COMMAND as MCP
from whiteboard.cli.commands.saves import DELETE_SAVE, LOAD, SAVE, SAVES
from whiteboard.cli.commands.serve import SERVE, STOP
from whiteboard.cli.commands.views import IDLE, KEYNOTES, NIGHT, TASKS, TODO

COMMANDS = (
    SERVE,
    STOP,
    MCP,
    CALIBRATE,
    FIT,
    ALIGN,
    REALIGN,
    LOOK,
    DRAW,
    CLEAR,
    SAVE,
    LOAD,
    SAVES,
    DELETE_SAVE,
    TODO,
    KEYNOTES,
    IDLE,
    TASKS,
    NIGHT,
    DISPLAYS,
    CAMERAS,
    CAMERA,
)

__all__ = ["COMMANDS"]
