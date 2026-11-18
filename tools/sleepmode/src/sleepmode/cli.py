"""The `sleepmode` command line: sleep, wake, status, mcp, plus the internal keeper command.

    sleepmode sleep [--wake 07:00]
    sleepmode wake
    sleepmode status
    sleepmode mcp          # the stdio MCP server (.mcp.json runs this)

`sleepmode keeper ...` is started by `sleep` and isn't for typing by hand. Every
command, the keeper included, appends to .state/sleepmode.log, and logs to stderr
when there is one.
"""

import argparse
import logging
import sys

from sleepmode.config import LOG_FILE
from sleepmode.control import SleepModeError, describe_sleep, describe_status, describe_wake
from sleepmode.keeper import KeeperOptions, run_keeper
from sleepmode.wiring import build_sleep_mode, night_view_for_keeper, read_state_for_keeper

log = logging.getLogger(__name__)

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
EXIT_FAILED = 1


def main(argv: list[str] | None = None) -> None:
    """Parse the arguments and run the command."""
    args = build_parser().parse_args(argv)
    _configure_logging()
    sys.exit(args.handler(args))


def build_parser() -> argparse.ArgumentParser:
    """The argument parser for every command, including the internal `keeper` one."""
    parser = argparse.ArgumentParser(prog="sleepmode", description="Sleep mode for the screens.")
    commands = parser.add_subparsers(dest="command", required=True)
    sleep = commands.add_parser("sleep", help="dark screens, night sky on the projector")
    sleep.add_argument("--wake", metavar="TIME", help="wake at TIME, e.g. 07:00, 7am or ISO")
    sleep.set_defaults(handler=_run_sleep)
    wake = commands.add_parser("wake", help="turn the screens back on")
    wake.add_argument("--reason", default="request", help=argparse.SUPPRESS)
    wake.set_defaults(handler=_run_wake)
    commands.add_parser("status", help="asleep or awake, and each display").set_defaults(
        handler=_run_status
    )
    commands.add_parser("mcp", help="serve the MCP tools on stdio").set_defaults(handler=_run_mcp)
    keeper = commands.add_parser("keeper")
    keeper.add_argument("--session", required=True)
    keeper.add_argument("--grace", type=float, required=True)
    keeper.add_argument("--keep-display-on", action="store_true")
    keeper.add_argument("--blackout", action="append", type=_rect, default=[])
    keeper.add_argument("--projector", type=_rect)
    # TODO: ignored; MCP servers started before the black-page option went (2026-11-18)
    # still pass it. Drop it once none of those can still be running (after an MCP restart).
    keeper.add_argument("--night-sky", action="store_true", help=argparse.SUPPRESS)
    keeper.set_defaults(handler=_run_keeper)
    return parser


def _run_sleep(args: argparse.Namespace) -> int:
    try:
        state = build_sleep_mode().sleep(wake_at=args.wake)
    except (ValueError, SleepModeError) as error:
        print(f"sleepmode: {error}", file=sys.stderr)
        return EXIT_FAILED
    print(describe_sleep(state))
    return 0


def _run_wake(args: argparse.Namespace) -> int:
    print(describe_wake(build_sleep_mode().wake(reason=args.reason)))
    return 0


def _run_status(_args: argparse.Namespace) -> int:
    try:
        print(describe_status(build_sleep_mode().status()))
    except SleepModeError as error:
        print(f"sleepmode: {error}", file=sys.stderr)
        return EXIT_FAILED
    return 0


def _run_mcp(_args: argparse.Namespace) -> int:
    # Imported here so the other commands (the wake task, the keeper) don't load the MCP SDK.
    from sleepmode.mcp_server import run_stdio_server

    run_stdio_server(build_sleep_mode())
    return 0


def _run_keeper(args: argparse.Namespace) -> int:
    options = KeeperOptions(
        args.session,
        tuple(args.blackout),
        args.keep_display_on,
        args.grace,
        args.projector,
    )
    try:
        sleep_mode = build_sleep_mode()
        run_keeper(
            options,
            read_state_for_keeper,
            lambda reason, session: sleep_mode.wake(reason=reason, only_session=session),
            night_view_for_keeper(),
        )
    except Exception:
        # The keeper's stderr goes nowhere, so a crash has to reach the log file.
        log.exception("the keeper crashed")
        return EXIT_FAILED
    return 0


def _rect(text: str) -> tuple[int, int, int, int]:
    """Parse "x,y,width,height" (physical pixels) for --blackout."""
    parts = text.split(",")
    try:
        x, y, width, height = (int(part) for part in parts)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"expected x,y,width,height, got {text!r}") from error
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError(f"width and height must be positive in {text!r}")
    return x, y, width, height


def _configure_logging() -> None:
    handlers: list[logging.Handler] = []
    if sys.stderr is not None:  # pythonw (the wake task) has no stderr
        handlers.append(logging.StreamHandler())
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Append mode: each process (CLI, MCP server, keeper, wake task) adds at the end.
    handlers.append(logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=handlers)
