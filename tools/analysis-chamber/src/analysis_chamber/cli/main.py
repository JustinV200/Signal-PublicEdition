"""`analysis-chamber` entry point: the argument parser and dispatch (handlers: commands.py)."""

import argparse
from collections.abc import Callable, Sequence

from analysis_chamber.cli import commands

Handler = Callable[[argparse.Namespace], int]


def build_parser() -> argparse.ArgumentParser:
    """Build the parser with every subcommand; each sets `handler` to its function."""
    parser = argparse.ArgumentParser(
        prog="analysis-chamber", description="Plan, run and question deep analyses."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, handler: Handler, help_text: str) -> argparse.ArgumentParser:
        subparser = sub.add_parser(name, help=help_text)
        subparser.set_defaults(handler=handler)
        return subparser

    add("serve", commands.serve, "run the daemon")
    add("mcp", commands.mcp, "serve the chamber MCP tools on stdio")
    add("list", commands.list_runs, "list runs")
    add("cancel", commands.cancel, "cancel a run").add_argument("run_id")
    add("start", commands.start, "draft a plan").add_argument("question")
    add("status", commands.status, "show a run's status").add_argument("run_id")
    add("check", commands.check, "health check: kit built and daemon answering (JSON line)")
    approve = add("approve", commands.approve, "approve a plan or send edits")
    approve.add_argument("run_id")
    approve.add_argument("--edits", default=None, help="plan changes; keeps the plan unapproved")
    approve.add_argument("--personal", choices=["yes", "no"], default=None)
    ask = add("ask", commands.ask, "ask a question about a run")
    ask.add_argument("run_id")
    ask.add_argument("question")
    add("gpu", commands.gpu, "run a command holding the GPU lock").add_argument(
        "cmd", nargs=argparse.REMAINDER, help="-- <cmd...>"
    )
    install = add("install", commands.install, "install packages into this run's venv (cwd)")
    install.add_argument("--allow-shadow", action="store_true", help="may replace kit versions")
    install.add_argument("packages", nargs="+")
    kit = sub.add_parser("kit", help="manage the analysis kit")
    kit_sub = kit.add_subparsers(dest="kit_command", required=True)
    kit_sub.add_parser("build", help="build or update the kit venv").set_defaults(
        handler=commands.kit_build
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the command line and run the subcommand.

    Args:
        argv: Arguments without the program name; None means sys.argv.

    Returns:
        The process exit code.
    """
    args = build_parser().parse_args(argv)
    return args.handler(args)
