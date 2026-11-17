"""Handlers for the `analysis-chamber` subcommands. Each takes parsed args, returns an exit code.

daemon, gpu, kit and mcp_server are imported inside the handlers so the CLI loads
(and `--help` works) without them.
"""

import argparse
import importlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from analysis_chamber.config import load_config
from analysis_chamber.runs import MANIFEST_NAME

EXIT_FAILED = 1
EXIT_USAGE = 2


def _client_call(call: Callable[[Any], Any]) -> int:
    """Build a DaemonClient, run `call(client)`, print its dict; DaemonError -> stderr, exit 1."""
    daemon = importlib.import_module("analysis_chamber.daemon")
    try:
        client = daemon.DaemonClient(load_config().state_dir)
        print(json.dumps(call(client), indent=2))
    except daemon.DaemonError as error:
        print(f"analysis-chamber: {error}", file=sys.stderr)
        return EXIT_FAILED
    return 0


def start(args: argparse.Namespace) -> int:
    """Draft a plan for the question."""
    return _client_call(lambda client: client.start(args.question))


def approve(args: argparse.Namespace) -> int:
    """Approve a plan or send edits; --personal yes/no becomes a bool."""
    personal = None if args.personal is None else args.personal == "yes"
    return _client_call(
        lambda client: client.approve(args.run_id, edits=args.edits, personal=personal)
    )


def status(args: argparse.Namespace) -> int:
    """Print one run's status."""
    return _client_call(lambda client: client.status(args.run_id))


def list_runs(args: argparse.Namespace) -> int:
    """Print every run."""
    return _client_call(lambda client: client.list())


def ask(args: argparse.Namespace) -> int:
    """Ask a question about a run."""
    return _client_call(lambda client: client.ask(args.run_id, args.question))


def cancel(args: argparse.Namespace) -> int:
    """Cancel a run."""
    return _client_call(lambda client: client.cancel(args.run_id))


def serve(args: argparse.Namespace) -> int:
    """Run the daemon until it is stopped."""
    daemon = importlib.import_module("analysis_chamber.daemon")
    daemon.serve(load_config())
    return 0


def mcp(args: argparse.Namespace) -> int:
    """Serve the five chamber tools on stdio."""
    from analysis_chamber.mcp_server import run_stdio_server

    run_stdio_server(load_config().state_dir)
    return 0


def gpu(args: argparse.Namespace) -> int:
    """Run a command holding the GPU lock; return its exit code."""
    from analysis_chamber.gpu import run_locked

    command = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not command:
        print("analysis-chamber gpu: give a command after --", file=sys.stderr)
        return EXIT_USAGE
    try:
        return run_locked(load_config().state_dir, command)
    except OSError as error:  # the command couldn't start
        print(f"analysis-chamber gpu: {error}", file=sys.stderr)
        return EXIT_FAILED


def kit_build(args: argparse.Namespace) -> int:
    """Build or update the shared analysis kit venv."""
    from analysis_chamber.kit import KitError, build_kit

    try:
        build_kit(load_config())
    except (KitError, OSError) as error:
        print(f"analysis-chamber: {error}", file=sys.stderr)
        return EXIT_FAILED
    return 0


def install(args: argparse.Namespace) -> int:
    """Install packages into the current folder's run venv (the folder must be a run)."""
    from analysis_chamber.kit import KitError, install_into_run_venv

    run_dir = Path.cwd()
    if not (run_dir / MANIFEST_NAME).is_file():
        print(
            f"analysis-chamber: no {MANIFEST_NAME} in {run_dir}; run from a run folder.",
            file=sys.stderr,
        )
        return EXIT_FAILED
    try:
        landed = install_into_run_venv(
            run_dir, load_config(), args.packages, allow_shadow=args.allow_shadow
        )
    except (KitError, OSError) as error:
        print(f"analysis-chamber: {error}", file=sys.stderr)
        return EXIT_FAILED
    print(json.dumps(landed, indent=2))
    return 0
