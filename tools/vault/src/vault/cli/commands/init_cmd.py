"""`vault init [--unlock hello|passphrase]`: create an empty vault bound to one unlock method.

Hello is the default. The passphrase fallback must be chosen explicitly; if
Hello isn't available, init fails and says so rather than switching methods.
An existing vault is never overwritten.
"""

import argparse
import asyncio

from vault.audit import EVENT_INIT
from vault.cli.context import CliContext
from vault.cli.terminal import CliError, require_interactive_stdin
from vault.store import create_vault_data, save_vault, vault_exists
from vault.unlock import PROVIDER_HELLO, PROVIDERS, UnlockError

NAME = "init"
HELP = "Create the vault and choose how it unlocks (Windows Hello, or a passphrase)."
RESULT_OK = "ok"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add init's options."""
    parser.add_argument(
        "--unlock",
        choices=PROVIDERS,
        default=PROVIDER_HELLO,
        help="hello (default): Windows Hello on every fill. passphrase: passphrase dialog + DPAPI.",
    )


def run(args: argparse.Namespace, context: CliContext) -> int:
    """Create the vault. Returns the exit code.

    Raises:
        CliError: Not a terminal, vault already exists, or the unlock method failed.
    """
    require_interactive_stdin(context.stdin)
    if vault_exists(context.store_path):
        raise CliError(
            f"a vault already exists at {context.store_path}; delete it yourself to start over"
        )
    unlocker = context.unlocker_for(args.unlock)
    try:
        data = asyncio.run(create_vault_data(unlocker))
    except UnlockError as error:
        hint = " (to use a passphrase instead: vault init --unlock passphrase)"
        raise CliError(f"{error}{hint if args.unlock == PROVIDER_HELLO else ''}") from None
    save_vault(context.store_path, data)
    context.audit.record(EVENT_INIT, "", RESULT_OK)
    context.out(f"created vault ({args.unlock} unlock) at {context.store_path}")
    return 0
