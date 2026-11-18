"""`console` command line: parse the subcommand, run it, print any error on one line.

The orchestrator runs these to carry out what the owner asks for in the console
(e.g. `console hub start`), runs `console claim` once per session, and
reports its tasks with `console tasks set|done|rm|show`. `console doctor` checks the setup.
"""

import argparse
import logging
import sys

from signal_console.cli.commands import run_claim, run_hub, run_serve
from signal_console.cli.doctor_command import run_doctor
from signal_console.cli.open_command import open_console
from signal_console.cli.server_log import LOG_FORMAT, print_to_server_log
from signal_console.cli.tasks_command import add_tasks_parser
from signal_console.health import HealthPaths
from signal_console.paths import DEFAULT_PORT, STATE_DIR


def main(argv: list[str] | None = None) -> int:
    """Run one `console` command. Returns the process exit code."""
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    try:
        # Inside the try: building the parser reads .env (the tasks help names the owner).
        args = _parser().parse_args(argv)
        return args.run(args)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"console: {error}", file=sys.stderr)
        return 1


def _run_open(args: argparse.Namespace) -> int:
    if sys.stdout is None:
        # pythonw (the Start-menu shortcut) has no console: open's words go to server.log.
        print_to_server_log(STATE_DIR)
        # The log handler was made before this, with no stderr: remake it on server.log.
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, force=True)
    paths = HealthPaths(state_dir=STATE_DIR, default_port=args.port)
    page = open_console(paths, args.view, args.tool)
    print(f"Opening the console at {page}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="console", description="The Signal console.")
    commands = parser.add_subparsers(required=True, metavar="command")

    serve = commands.add_parser("serve", help="run the console server in the foreground")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve.set_defaults(run=run_serve)

    open_page = commands.add_parser("open", help="start the server if needed and open the page")
    open_page.add_argument("--port", type=int, default=DEFAULT_PORT, help="port for a new server")
    open_page.add_argument("--view", help="open on this view, e.g. setup or system")
    open_page.add_argument("--tool", help="with --view setup: open the wizard at this tool")
    open_page.set_defaults(run=_run_open)

    claim = commands.add_parser("claim", help="link this Claude Code session to the console")
    claim.add_argument("--label", help="a name to show in the console")
    claim.set_defaults(run=run_claim)

    hub = commands.add_parser("hub", help="start, stop or check Voice")
    hub.add_argument("hub_command", choices=["start", "stop", "status"])
    hub.set_defaults(run=run_hub)

    doctor = commands.add_parser("doctor", help="check the console's setup (read-only)")
    doctor.add_argument(
        "--summary-json",
        action="store_true",
        help="end with the first fail row as one JSON line (for setup's check)",
    )
    doctor.set_defaults(run=run_doctor)

    add_tasks_parser(commands)
    return parser
