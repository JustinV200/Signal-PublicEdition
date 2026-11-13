"""`vault` entry point (owner-only CLI): parses the subcommand and runs it.

There is no show, export or reveal command. Errors the owner can fix print one
line; none of them ever contains a secret.
"""

import argparse
import sys
from collections.abc import Sequence
from typing import NoReturn

from vault.cli.commands import COMMANDS
from vault.cli.context import CliContext, default_context
from vault.cli.terminal import CliError
from vault.store import VaultFormatError, VaultNotInitializedError

EXIT_USER_ERROR = 2
# Conventional exit code for a process ended by Ctrl+C (128 + SIGINT).
EXIT_INTERRUPTED = 130

PASSWORD_REFUSAL = (
    "vault: Passwords are never accepted on the command line (they'd be saved in your shell "
    "history). Run the command without --password and you'll be prompted (hidden input). "
    "If you already typed a real password in a command, change it and clear your shell history."
)

_USER_ERRORS = (CliError, VaultFormatError, VaultNotInitializedError)


def build_parser() -> argparse.ArgumentParser:
    """Build the parser with one subparser per registered command."""
    parser = _QuietParser(
        prog="vault",
        description="Owner-only management of the Signal credential vault. Run it yourself.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for command in COMMANDS:
        command.add_arguments(
            subparsers.add_parser(command.NAME, help=command.HELP, description=command.HELP)
        )
    return parser


def _has_password_flag(argv: Sequence[str]) -> bool:
    """True for anything that could be a password option: -p/-P (any value), --p*, /p* (any case).

    No real vault option starts with --p, so this errs on the side of refusing.
    """
    for arg in argv:
        lowered = arg.lower()
        name = lowered.split("=", 1)[0]
        if name.startswith("--p") or lowered.startswith(("/p", "-p")):
            return True
    return False


class _QuietParser(argparse.ArgumentParser):
    """Never echoes the offending arguments: they might be a secret typed by mistake."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        print(f"vault: bad or unknown option; run `{self.prog} --help`.", file=sys.stderr)
        raise SystemExit(EXIT_USER_ERROR)


def main(argv: Sequence[str] | None = None, context: CliContext | None = None) -> int:
    """Parse arguments and run the chosen command.

    Args:
        argv: Arguments without the program name (default: sys.argv[1:]).
        context: Files, prompts and streams (default: the real ones).

    Returns:
        The process exit code.
    """
    arguments = sys.argv[1:] if argv is None else argv
    # Before argparse, so the value never reaches its error output.
    if _has_password_flag(arguments):
        print(PASSWORD_REFUSAL, file=sys.stderr)
        return EXIT_USER_ERROR
    args = build_parser().parse_args(arguments)
    command = next(command for command in COMMANDS if args.command == command.NAME)
    try:
        return command.run(args, context or default_context())
    except _USER_ERRORS as error:
        print(f"vault: {error}", file=sys.stderr)
        return EXIT_USER_ERROR
    except KeyboardInterrupt:
        print("vault: interrupted", file=sys.stderr)
        return EXIT_INTERRUPTED
