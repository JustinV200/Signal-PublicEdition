"""`mail` entry point: builds the argparse parser and runs the chosen command.

Errors the owner can act on (setup, unknown account, re-auth, offline, Gmail
errors) print one clean line instead of a traceback. Logging goes to stderr,
because in `mail mcp` stdout is the protocol channel.
"""

import argparse
import logging
import sys
from collections.abc import Sequence

from mail_tool.cli import check, commands
from mail_tool.cli.setup_guide import run_setup
from mail_tool.errors import MailError
from mail_tool.service import DEFAULT_MAX_RESULTS, SELF_ADDRESS

EXIT_USER_ERROR = 2
# Conventional exit code for a process ended by Ctrl+C (128 + SIGINT).
EXIT_INTERRUPTED = 130
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def build_parser() -> argparse.ArgumentParser:
    """The `mail` parser with every subcommand; parsed args carry `handler`."""
    parser = argparse.ArgumentParser(prog="mail", description="Claude's Gmail accounts tool.")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    sub.add_parser("setup", help="print the Google Cloud steps and check the client file")
    add = sub.add_parser("add", help="sign an account in through the browser")
    add.add_argument("alias", help="short name, e.g. personal")
    add.add_argument("--email", help="the address you expect to sign in as (checked)")
    sub.add_parser("accounts", help="list accounts and their status")
    sub.add_parser("check", help="offline health check of the saved sign-ins (exit 1 if not fine)")
    remove = sub.add_parser("remove", help="forget an account's saved sign-in")
    remove.add_argument("alias")
    search = sub.add_parser("search", help="search with Gmail query syntax")
    search.add_argument("account", help="alias or email address")
    search.add_argument("query", help="e.g. 'is:unread newer_than:1d'")
    search.add_argument("--max", type=int, default=DEFAULT_MAX_RESULTS, help="1-50")
    search.add_argument(
        "--paged", action="store_true", help="print the paged envelope (first page)"
    )
    search.add_argument(
        "--page-token", default="", help="next_page_token from a previous page (implies --paged)"
    )
    read = sub.add_parser("read", help="read one message")
    read.add_argument("account", help="alias or email address")
    read.add_argument("message_id")
    # No recipient option on purpose: send-self only ever mails SELF_ADDRESS.
    send_self = sub.add_parser(
        "send-self", help=f"email a plain-text file to {SELF_ADDRESS}, no dialog"
    )
    send_self.add_argument("--subject", required=True)
    send_self.add_argument("--body-file", required=True, help="UTF-8 text file")
    sub.add_parser("mcp", help="run the stdio MCP server")

    handlers = {
        "setup": lambda _args: run_setup(),
        "add": commands.add_account,
        "accounts": commands.list_accounts,
        "check": check.check_accounts,
        "remove": commands.remove_account,
        "search": commands.search,
        "read": commands.read,
        "send-self": commands.send_self,
        "mcp": commands.serve_mcp,
    }
    for name, handler in handlers.items():
        sub.choices[name].set_defaults(handler=handler)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and run the command.

    Args:
        argv: Arguments without the program name (default sys.argv[1:]).

    Returns:
        The process exit code.
    """
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stderr)
    # Email text can hold characters a legacy console code page can't print.
    sys.stdout.reconfigure(errors="replace")
    try:
        return args.handler(args)
    except MailError as error:
        print(f"mail: error: {error}", file=sys.stderr)
        return EXIT_USER_ERROR
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
