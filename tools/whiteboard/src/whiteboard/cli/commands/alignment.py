"""`whiteboard calibrate | fit | align | realign`: line the camera and projection up with the board.

calibrate maps camera to projector with ArUco markers and then auto-fits the
board outline; fit re-detects, shows or clears that outline, or takes a
manual --quad when auto-detection fails; align measures how far the board has
drifted from the fit, and realign flashes the markers and re-aligns if anything
moved (the daemon also does both by itself, see [align]).
"""

import argparse
import json

from whiteboard.cli.command import EXIT_FAILED, EXIT_OK, Command, daemon_connection, no_arguments
from whiteboard.config import Settings
from whiteboard.daemon_client import FIT_MODES, quad_from_numbers, send_fit


def run_calibrate(args: argparse.Namespace, settings: Settings) -> int:
    """Run calibration and print the outcome; exit 1 when the markers weren't found."""
    result = daemon_connection(args, settings).call(lambda api: api.calibrate())
    if not result.get("ok"):
        print(f"calibration failed: {result.get('error', 'unknown error')}")
        return EXIT_FAILED
    print(f"calibrated: reprojection error {result.get('reprojection_error_px')} px")
    if result.get("board_found"):
        print(f"board outline found and fitted: {json.dumps(result.get('board_quad'))}")
    else:
        reason = result.get("board_error") or "not detected"
        print(f"board outline not fitted ({reason}); try `whiteboard fit --quad ...`")
    return EXIT_OK


def add_fit_arguments(parser: argparse.ArgumentParser) -> None:
    """`fit` arguments: a mode, or a manual --quad."""
    parser.add_argument("mode", nargs="?", default="auto", choices=FIT_MODES)
    parser.add_argument(
        "--quad",
        type=parse_quad,
        metavar="X1,Y1,...,X4,Y4",
        help="board corners in projector pixels, clockwise from top-left (overrides mode)",
    )


def parse_quad(text: str) -> list[list[float]]:
    """Parse "x1,y1,x2,y2,x3,y3,x4,y4" into four [x, y] corners.

    Raises:
        argparse.ArgumentTypeError: Not eight numbers.
    """
    try:
        return quad_from_numbers([float(part) for part in text.split(",")])
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def run_fit(args: argparse.Namespace, settings: Settings) -> int:
    """Fit, show or clear the board quad and print the daemon's answer."""
    result = daemon_connection(args, settings).call(lambda api: send_fit(api, args.mode, args.quad))
    print(json.dumps(result))
    return EXIT_OK if result.get("ok", True) else EXIT_FAILED


def run_align(args: argparse.Namespace, settings: Settings) -> int:
    """Print the board's drift from the current fit; exit 1 when it couldn't be measured."""
    result = daemon_connection(args, settings).call(lambda api: api.align_check())
    if not result.get("ok"):
        print(f"drift check failed: {result.get('error', 'unknown error')}")
        return EXIT_FAILED
    if result.get("error_px") is None:
        print(f"no drift reading: {result.get('note')}")
        return EXIT_FAILED
    limit = settings.align.drift_px
    print(f"board drift: {result['error_px']} camera px (auto re-align over {limit:g} px)")
    return EXIT_OK


def run_realign(args: argparse.Namespace, settings: Settings) -> int:
    """Re-align now and print what changed; exit 1 when the old alignment was kept on a failure."""
    result = daemon_connection(args, settings).call(lambda api: api.realign())
    print(result.get("message", "no answer"))
    numbers = {key: value for key, value in result.items() if key.endswith("_px")}
    print(json.dumps(numbers))
    return EXIT_OK if result.get("ok") else EXIT_FAILED


CALIBRATE = Command(
    "calibrate", "calibrate camera to projector, then fit the board", no_arguments, run_calibrate
)
FIT = Command(
    "fit",
    "fit the projection to the board: auto | show | clear | --quad",
    add_fit_arguments,
    run_fit,
)
ALIGN = Command(
    "align",
    "measure how far the board has drifted from the fit (no re-align)",
    no_arguments,
    run_align,
)
REALIGN = Command(
    "realign",
    "flash the markers and re-align if the camera, projector or board moved",
    no_arguments,
    run_realign,
)
