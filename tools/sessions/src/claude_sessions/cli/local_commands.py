"""The CLI commands that run in-process: serve (the daemon), mcp (stdio server), repos, check.

serve and mcp are imported lazily, because the SDK and MCP packages add
noticeable start-up time to every other command.
"""

import argparse
import asyncio
import dataclasses
import json

from claude_sessions.cli.command import add_command, use_info_logging
from claude_sessions.cli.output import format_repos
from claude_sessions.config import Settings
from claude_sessions.ipc import DaemonStartError, is_daemon_running
from claude_sessions.repos import find_repos

EXIT_OK = 0
EXIT_FAILED = 1
# Well under the setup tool's 8 s health timeout, so a hung daemon gets our own words.
CHECK_PING_TIMEOUT_S = 4.0
NOT_ANSWERING_FIX = (
    "End the process holding the sessions daemon's port (a stale token or a hung daemon); "
    "the next request starts a fresh one."
)


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


def run_check(args: argparse.Namespace, settings: Settings) -> int:
    """`sessions check`: the setup tool's health check. Never starts the daemon.

    Prints one JSON line {words, fix, command} (tools/setup/README.md, "Verify
    checks"). Passes whether or not the daemon runs, since the first request starts it;
    exit 1 when something holds its port but doesn't answer as it (stale token, hung).
    """
    count = len(find_repos(settings.repo_roots, settings.max_depth))
    found = f"{count} repo{'' if count == 1 else 's'} found"
    try:
        is_running = asyncio.run(_ping(settings))
    except (DaemonStartError, TimeoutError):
        _print_check(f"{found}; daemon not answering", NOT_ANSWERING_FIX)
        return EXIT_FAILED
    daemon = "daemon running" if is_running else "daemon not running (starts on first use)"
    fix = None if count else "No git repos under the repo roots: set SESSIONS_REPO_ROOTS in .env."
    _print_check(f"{found}; {daemon}", fix)
    return EXIT_OK


async def _ping(settings: Settings) -> bool:
    """is_daemon_running, cut off after CHECK_PING_TIMEOUT_S (raises TimeoutError)."""
    return await asyncio.wait_for(is_daemon_running(settings), CHECK_PING_TIMEOUT_S)


def _print_check(words: str, fix: str | None) -> None:
    """Print run_check's one-line summary (there's never a command to run)."""
    print(json.dumps({"words": words, "fix": fix, "command": None}))


def add_local_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register serve, mcp, repos and check on the CLI's subparsers.

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
    add_command(subparsers, "check", "health check: repos and daemon, as a JSON line", run_check)
