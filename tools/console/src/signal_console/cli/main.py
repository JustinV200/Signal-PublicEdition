"""`console` command line: parse the subcommand, run it, print any error on one line.

The orchestrator runs these to carry out what the owner asks for in the console
(e.g. `console hub start`), runs `console claim` once per session, and
reports its tasks with `console tasks set|done|rm|show`.
"""

import argparse
import logging
import sys

from signal_console.cli.commands import run_claim, run_hub, run_serve
from signal_console.cli.open_command import open_console
from signal_console.cli.tasks_command import add_tasks_parser
from signal_console.paths import DEFAULT_PORT, STATE_DIR


def main(argv: list[str] | None = None) -> int:
    """Run one `console` command. Returns the process exit code."""
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    try:
        return args.run(args)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"console: {error}", file=sys.stderr)
        return 1


def _run_open(args: argparse.Namespace) -> int:
    page = open_console(STATE_DIR, args.port, args.view, args.tool)
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
    open_page.add_argument("--view", help="open on this view, e.g. setup or tools")
    open_page.add_argument("--tool", help="with --view setup: open the wizard at this tool")
    open_page.set_defaults(run=_run_open)

    claim = commands.add_parser("claim", help="make this Claude Code session the orchestrator")
    claim.add_argument("--label", help="a name to show in the console")
    claim.set_defaults(run=run_claim)

    hub = commands.add_parser("hub", help="start, stop or check the voice hub")
    hub.add_argument("hub_command", choices=["start", "stop", "status"])
    hub.set_defaults(run=run_hub)

    add_tasks_parser(commands)
    return parser
