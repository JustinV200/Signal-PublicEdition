"""The CLI commands that run in-process: serve (the daemon), mcp (the stdio server) and repos.

serve and mcp are imported lazily, because the SDK and MCP packages add
noticeable start-up time to every other command.
"""

import argparse
import asyncio
import dataclasses

from claude_sessions.cli.command import add_command, use_info_logging
from claude_sessions.cli.output import format_repos
from claude_sessions.config import Settings
from claude_sessions.repos import find_repos

EXIT_OK = 0


def run_serve(args: argparse.Namespace, settings: Settings) -> int:
    """`sessions serve`: run the daemon in this process until Ctrl+C or `sessions shutdown`."""
    from claude_sessions.daemon import serve

    if args.port is not None:
        settings = dataclasses.replace(settings, daemon_port=args.port)
    asyncio.run(serve(settings))
    return EXIT_OK


def run_mcp(args: argparse.Namespace, settings: Settings) -> int:
    """`sessions mcp`: the stdio MCP server; stdout is the protocol, so nothing is printed."""
    from claude_sessions.mcp import run_stdio_server

    run_stdio_server(settings)
    return EXIT_OK


def run_repos(args: argparse.Namespace, settings: Settings) -> int:
    """`sessions repos [QUERY]`: git repos under the configured roots."""
    repos = find_repos(settings.repo_roots, settings.max_depth)
    wanted = args.query.lower()
    print(format_repos([repo for repo in repos if wanted in repo.name.lower()]))
    return EXIT_OK


def add_local_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register serve, mcp and repos on the CLI's subparsers.

    Args:
        subparsers: From ArgumentParser.add_subparsers().
    """
    serve = add_command(subparsers, "serve", "run the sessions daemon (foreground)", run_serve)
    serve.add_argument("--port", type=int, default=None, help="override the daemon port")
    use_info_logging(serve)
    mcp = add_command(subparsers, "mcp", "run the stdio MCP server (for .mcp.json)", run_mcp)
    use_info_logging(mcp)
    repos = add_command(subparsers, "repos", "list git repos under the configured roots", run_repos)
    repos.add_argument("query", nargs="?", default="", help="filter on repo name")
