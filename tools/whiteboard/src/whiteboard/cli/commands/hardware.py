"""`whiteboard displays | cameras`: list the monitors and webcams, to pick the config values.

`cameras` opens each device, so stop the daemon first (it holds the camera).
"""

import argparse

from whiteboard.cli.command import EXIT_OK, Command, no_arguments
from whiteboard.config import Settings


def run_displays(args: argparse.Namespace, settings: Settings) -> int:
    """Print every monitor and mark the one the daemon would use as the projector."""
    # Imported here so other commands don't load the display package.
    from whiteboard.display.screen import ProjectorNotFoundError, list_monitors, pick_projector

    monitors = list_monitors()
    try:
        projector = pick_projector(monitors, settings.display.name_match)
    except ProjectorNotFoundError as error:
        print(f"no projector: {error}")
        projector = None
    for monitor in monitors:
        marks = [
            mark
            for mark, is_on in (
                ("primary", monitor.is_primary),
                ("PROJECTOR", monitor == projector),
            )
            if is_on
        ]
        print(
            f"{monitor.device_name}  {monitor.friendly_name or '?'}  "
            f"{monitor.width}x{monitor.height} at ({monitor.x},{monitor.y}) "
            f"scale {monitor.scale:g}  {' '.join(marks)}"
        )
    return EXIT_OK


def run_cameras(args: argparse.Namespace, settings: Settings) -> int:
    """Probe the webcams at the configured resolution and print what each delivers."""
    from whiteboard.camera import list_cameras

    cameras = list_cameras(settings.camera.width, settings.camera.height)
    if not cameras:
        print("no cameras found (is the daemon holding it? stop it first)")
    for camera in cameras:
        print(camera)
    return EXIT_OK


DISPLAYS = Command(
    "displays", "list monitors and show which is the projector", no_arguments, run_displays
)
CAMERAS = Command(
    "cameras", "list webcams and the resolution each delivers", no_arguments, run_cameras
)
