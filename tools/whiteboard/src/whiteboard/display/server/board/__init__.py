"""Public API of whiteboard.display.server.board: the BoardController and its page data.

BoardController (controller.py) builds on SceneBoard (scene_board.py, the saved and
broadcast scene); modes.py holds the display modes, Marker and Highlight.
"""

from whiteboard.display.server.board.controller import BoardController
from whiteboard.display.server.board.modes import DISPLAY_MODES, Highlight, Marker

__all__ = ["DISPLAY_MODES", "BoardController", "Highlight", "Marker"]
