"""`vault remove ID`: delete one credential after the owner retypes its id.

Removal unlocks the vault and re-seals every other credential under a fresh
data key (see store/rotation.py), so the removed record pasted back alone
can't be used. A full copy of the old store.json still opens with the same
unlock factor, so this is not a full revocation.
"""

import argparse
import asyncio

from vault.audit import EVENT_REMOVE
from vault.cli.context import CliContext
from vault.cli.terminal import CliError, require_interactive_stdin
from vault.crypto import DecryptionError
from vault.store import TamperedRecordError, load_vault, remove_and_rotate, save_vault
from vault.unlock import UnlockError

NAME = "remove"
HELP = "Delete a stored credential (re-keys the rest, so old copies stop working)."
RESULT_OK = "ok"
EXIT_CANCELLED = 1


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add remove's argument."""
    parser.add_argument("id", help="The credential id to delete.")


def run(args: argparse.Namespace, context: CliContext) -> int:
    """Remove the credential and rotate the data key. Returns the exit code.

    Raises:
        CliError: Not a terminal, no such credential, unlock failed, or a
            remaining record doesn't verify (the store is left unchanged).
    """
    require_interactive_stdin(context.stdin)
    data = load_vault(context.store_path)
    if data.find(args.id) is None:
        raise CliError(f"no credential named {args.id!r}")
    if context.ask_line(f"Type '{args.id}' to delete it: ").strip() != args.id:
        context.out("not removed")
        return EXIT_CANCELLED
    unlocker = context.unlocker_for(data.header.provider)
    try:
        rotated = asyncio.run(remove_and_rotate(data, args.id, unlocker))
    except (UnlockError, DecryptionError):
        raise CliError("could not unlock the vault; nothing was removed") from None
    except TamperedRecordError as error:
        raise CliError(f"{error}; nothing was removed") from None
    save_vault(context.store_path, rotated)
    context.audit.record(EVENT_REMOVE, args.id, RESULT_OK)
    context.out(f"removed {args.id}")
    return 0
