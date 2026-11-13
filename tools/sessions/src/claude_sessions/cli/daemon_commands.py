"""The CLI commands that talk to the daemon: list, start, send, status, resume, stop, shutdown.

Each one makes a single daemon request through ipc.call_running_daemon, which
starts the daemon in the background first if it isn't running (except
shutdown, which never starts one just to stop it).
"""

import argparse
import asyncio
from typing import Any

from claude_sessions.cli.command import add_command
from claude_sessions.cli.output import format_sessions, format_status
from claude_sessions.config import Settings
from claude_sessions.ipc import (
    DaemonNotRunningError,
    call_daemon,
    call_running_daemon,
    daemon_endpoint,
)
from claude_sessions.repos import locate_repo

EXIT_OK = 0
DEFAULT_STATUS_TEXTS = 3


def run_list(args: argparse.Namespace, settings: Settings) -> int:
    """`sessions list`: every managed session, newest first."""
    print(format_sessions(_call(settings, "list", {})))
    return EXIT_OK


def run_start(args: argparse.Namespace, settings: Settings) -> int:
    """`sessions start REPO PROMPT`: start a session; prints its status (with the id)."""
    repo_path = locate_repo(args.repo, settings.repo_roots, settings.max_depth)
    request: dict[str, Any] = {
        "repo": str(repo_path),
        "prompt": args.prompt,
        "permission_mode": args.mode,
    }
    if args.model:
        request["model"] = args.model
    print(format_status(_call(settings, "start", request)))
    return EXIT_OK


def run_send(args: argparse.Namespace, settings: Settings) -> int:
    """`sessions send ID PROMPT`: send a follow-up prompt to an idle session."""
    print(format_status(_call(settings, "send", {"id": args.id, "prompt": args.prompt})))
    return EXIT_OK


def run_status(args: argparse.Namespace, settings: Settings) -> int:
    """`sessions status ID`: state, cost and the newest replies."""
    request = {"id": args.id, "last_n": args.last}
    print(format_status(_call(settings, "status", request)))
    return EXIT_OK


def run_resume(args: argparse.Namespace, settings: Settings) -> int:
    """`sessions resume SESSION PROMPT`: continue a stopped or past session."""
    request = {"session": args.session, "prompt": args.prompt}
    print(format_status(_call(settings, "resume", request)))
    return EXIT_OK


def run_stop(args: argparse.Namespace, settings: Settings) -> int:
    """`sessions stop ID`: stop a session's CLI process."""
    print(format_status(_call(settings, "stop", {"id": args.id})))
    return EXIT_OK


def run_shutdown(args: argparse.Namespace, settings: Settings) -> int:
    """`sessions shutdown`: stop every session and the daemon itself."""
    endpoint = daemon_endpoint(settings)
    try:
        if endpoint is None:
            raise DaemonNotRunningError("no token file")
        asyncio.run(call_daemon(endpoint, "shutdown"))
    except DaemonNotRunningError:
        print("The sessions daemon isn't running.")
        return EXIT_OK
    print("The sessions daemon is stopping its sessions and shutting down.")
    return EXIT_OK


def add_daemon_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register every daemon command and its arguments on the CLI's subparsers.

    Args:
        subparsers: From ArgumentParser.add_subparsers().
    """
    add_command(subparsers, "list", "list managed sessions", run_list)
    start = add_command(subparsers, "start", "start a session in a repo (path or name)", run_start)
    start.add_argument("repo", help="repo path, or a repo name or unique part of one")
    start.add_argument("prompt", help="the first prompt")
    start.add_argument("--model", default="", help='model or alias, e.g. "sonnet"')
    start.add_argument("--mode", default="default", help="default, acceptEdits or plan")
    send = add_command(subparsers, "send", "send a prompt to an idle session", run_send)
    send.add_argument("id")
    send.add_argument("prompt")
    status = add_command(
        subparsers, "status", "show a session's state and newest replies", run_status
    )
    status.add_argument("id")
    status.add_argument("--last", type=int, default=DEFAULT_STATUS_TEXTS, help="replies to show")
    resume = add_command(subparsers, "resume", "continue a stopped or past session", run_resume)
    resume.add_argument("session", help="managed id or Claude session id")
    resume.add_argument("prompt")
    stop = add_command(subparsers, "stop", "stop a session", run_stop)
    stop.add_argument("id")
    add_command(subparsers, "shutdown", "stop all sessions and the daemon", run_shutdown)


def _call(settings: Settings, op: str, args: dict[str, Any]) -> Any:
    """Run one daemon request from synchronous CLI code."""
    return asyncio.run(call_running_daemon(settings, op, args))
