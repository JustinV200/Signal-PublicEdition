"""The `brief` command line: show the brief, away mode, and the MCP server.

    brief show [--plain]               # the brief (never acks: see below)
    brief away on [--until SUNDAY] [--note TEXT]
    brief away off
    brief away status
    brief mcp                          # the stdio MCP server (.mcp.json runs this)

`show` prints markdown on a terminal and, when stdout isn't one (a model ran it),
one trusted line plus the framed brief. `--plain` prints the markdown even when
piped, for callers whose output goes only to the owner, never to a model. It
isn't a delivery and there's no CLI ack: only a surface that knows the owner saw
the brief may ack it.
"""

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Coroutine
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from signal_brief import BRIEF_TAG, BriefPaths, compose, render_model, render_text
from signal_untrusted import framed

from brief_tool.mcp_server import AwayTools, BriefTools, build_server
from brief_tool.surface import brief_surface
from brief_tool.wording import CLI_BRIEF_LINE

EXIT_FAILED = 1


def main(argv: list[str] | None = None) -> None:
    """Parse the arguments and run the command."""
    args = build_parser().parse_args(argv)
    # stdout is the MCP channel for `brief mcp`, so logs only ever go to stderr.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    sys.exit(args.handler(args))


def build_parser() -> argparse.ArgumentParser:
    """The argument parser for every command."""
    parser = argparse.ArgumentParser(prog="brief", description="The owner's catch-up brief.")
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("show", help="print the brief")
    show.add_argument(
        "--plain", action="store_true", help="unframed markdown even when piped (not for models)"
    )
    show.set_defaults(handler=_run_show)
    away = commands.add_parser("away", help="away mode").add_subparsers(dest="away", required=True)
    on = away.add_parser("on", help="turn away mode on")
    on.add_argument("--until", default="", help='e.g. "sunday", "tomorrow", 2026-10-25')
    on.add_argument("--note", default="", help="a short note")
    on.set_defaults(handler=_run_away_on)
    away.add_parser("off", help="turn away mode off").set_defaults(handler=_run_away_off)
    away.add_parser("status", help="away, asleep or here").set_defaults(handler=_run_away_status)
    commands.add_parser("mcp", help="serve the MCP tools on stdio").set_defaults(handler=_run_mcp)
    return parser


def _run_show(args: argparse.Namespace) -> int:
    brief = compose(BriefPaths())
    if args.plain or sys.stdout.isatty():
        print(render_text(brief).body)
    else:
        print(framed(CLI_BRIEF_LINE, render_model(brief).body, BRIEF_TAG))
    return 0


def _run_away_on(args: argparse.Namespace) -> int:
    return _print_tool_result(AwayTools(BriefPaths()).away_on(args.until, args.note))


def _run_away_off(_: argparse.Namespace) -> int:
    return _print_tool_result(AwayTools(BriefPaths()).away_off())


def _run_away_status(_: argparse.Namespace) -> int:
    return _print_tool_result(AwayTools(BriefPaths()).away_status())


def _print_tool_result(call: Coroutine[Any, Any, str]) -> int:
    """Run one AwayTools call and print its answer, so the CLI says what the tools say."""
    try:
        print(asyncio.run(call))
    except ToolError as error:
        print(f"brief: {error}", file=sys.stderr)
        return EXIT_FAILED
    return 0


def _run_mcp(_: argparse.Namespace) -> int:
    paths = BriefPaths()
    build_server(BriefTools(paths, brief_surface(os.environ)), AwayTools(paths)).run("stdio")
    return 0
