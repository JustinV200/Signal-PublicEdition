"""The `mail` subcommand handlers (all but setup): add, accounts, remove, search, read,
send-self, mcp.

Each takes the parsed argparse namespace and returns an exit code. MailErrors
propagate to main(), which prints them as one line.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from mail_tool.auth import TokenStore
from mail_tool.config import ACCOUNTS_DIR, CLIENT_SECRETS_PATH
from mail_tool.errors import MailError
from mail_tool.mcp_server import run_stdio_server
from mail_tool.service import AccountSignIn, build_service

EXIT_OK = 0
EXIT_NOT_FOUND = 2
REVOKE_URL = "https://myaccount.google.com/permissions"


def add_account(args: argparse.Namespace) -> int:
    """`mail add ALIAS [--email ADDRESS]`: sign in through the browser and save the account."""
    sign_in = AccountSignIn(TokenStore(ACCOUNTS_DIR), CLIENT_SECRETS_PATH)
    record = sign_in.add(args.alias, args.email)
    print(f"Saved {record.alias!r} ({record.email}).")
    return EXIT_OK


def list_accounts(args: argparse.Namespace) -> int:
    """`mail accounts`: one line per account with its live status."""
    rows = build_service().list_accounts()
    if not rows:
        print("No accounts configured. Add one with `mail add <alias> --email <address>`.")
        return EXIT_OK
    for row in rows:
        detail = f"  ({row['detail']})" if row.get("detail") else ""
        print(f"{row['alias']:<12} {row['email'] or '?':<32} {row['status']}{detail}")
    return EXIT_OK


def remove_account(args: argparse.Namespace) -> int:
    """`mail remove ALIAS`: delete the saved sign-in (Google access stays until revoked)."""
    if not TokenStore(ACCOUNTS_DIR).remove(args.alias):
        print(f"No account {args.alias!r}.")
        return EXIT_NOT_FOUND
    print(f"Removed {args.alias!r}. To also revoke the app's access at Google: {REVOKE_URL}")
    return EXIT_OK


def search(args: argparse.Namespace) -> int:
    """`mail search ACCOUNT QUERY [--max N] [--paged | --page-token T]`: print summaries as JSON.

    The default output is a bare list (mail-digest parses it). --paged or --page-token prints
    the {messages, next_page_token?, estimated_total?} envelope instead.
    """
    service = build_service()
    if args.paged or args.page_token:
        result = service.search_page(args.account, args.query, args.max, args.page_token)
    else:
        result = service.search(args.account, args.query, args.max)
    _print_json(result)
    return EXIT_OK


def read(args: argparse.Namespace) -> int:
    """`mail read ACCOUNT ID`: print one message as JSON."""
    _print_json(build_service().read(args.account, args.message_id))
    return EXIT_OK


def send_self(args: argparse.Namespace) -> int:
    """`mail send-self --subject S --body-file F`: email the body to SELF_ADDRESS, no dialog.

    Raises:
        MailError: The body file can't be read as UTF-8, or as MailService.send_to_self.
    """
    try:
        body = Path(args.body_file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise MailError(f"Can't read the body file: {error}") from None
    result = build_service().send_to_self(args.subject, body)
    print(f"Sent to {result['to']} (message {result['message_id']}).")
    return EXIT_OK


def serve_mcp(args: argparse.Namespace) -> int:
    """`mail mcp`: run the stdio MCP server until stdin closes."""
    run_stdio_server()
    return EXIT_OK


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))
