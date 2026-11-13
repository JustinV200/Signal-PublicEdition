"""`whiteboard camera view`: watch the webcam live in a local window, to aim it at the board.

It reads the daemon's GET /api/camera/stream through DaemonApi, so the token goes
in a header, never a URL, and the camera is never opened a second time. The view is
raw (no rectification) and nothing flashes on the board. q, Esc or closing the
window ends it. Like the board commands, it starts the daemon if it isn't running.
"""

import argparse
from typing import BinaryIO

from whiteboard.cli.command import EXIT_OK, Command, daemon_connection
from whiteboard.config import Settings

CAMERA_ACTIONS = ("view",)
WINDOW_TITLE = "whiteboard camera (q to quit)"
QUIT_KEYS = (ord("q"), ord("Q"), 27)  # 27 is Esc
# waitKey needs at least 1 ms to pump window events; frames come every ~200 ms anyway.
KEY_WAIT_MS = 1


def add_camera_arguments(parser: argparse.ArgumentParser) -> None:
    """ACTION (only `view` for now)."""
    parser.add_argument("action", choices=CAMERA_ACTIONS, help="view: a live camera window")


def run_camera(args: argparse.Namespace, settings: Settings) -> int:
    """Open the stream and show it until the window is closed or q is pressed."""
    # OpenCV is imported here so other commands start quickly.
    import cv2

    connection = daemon_connection(args, settings)
    try:
        with connection.call(lambda api: api.open_camera_stream()) as stream:
            # Only once the daemon said yes, so a 503 prints one line and no empty window.
            cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
            if _show_frames(stream):
                return EXIT_OK
        print("the camera stream ended (daemon stopped, or the camera went away)")
        return EXIT_OK
    finally:
        cv2.destroyAllWindows()


def _show_frames(stream: BinaryIO) -> bool:
    """Show each frame of the open stream; True if the viewer quit, False if it ended.

    A read that times out or a dropped connection (both OSError) counts as the
    stream ending. Only the reads are covered, so a daemon that can't be reached
    at all still reports its own error.
    """
    import cv2
    import numpy as np

    from whiteboard.daemon_client import iter_jpeg_parts

    try:
        for jpeg in iter_jpeg_parts(stream):
            frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            cv2.imshow(WINDOW_TITLE, frame)
            if _should_quit():
                return True
    except OSError:
        pass  # Reported by the caller as the stream ending.
    return False


def _should_quit() -> bool:
    """Pump window events; True on a quit key or once the window was closed."""
    import cv2

    key = cv2.waitKey(KEY_WAIT_MS) & 0xFF
    is_closed = cv2.getWindowProperty(WINDOW_TITLE, cv2.WND_PROP_VISIBLE) < 1
    return key in QUIT_KEYS or is_closed


CAMERA = Command(
    "camera",
    "camera view: watch the webcam live in a window, to aim it",
    add_camera_arguments,
    run_camera,
)
