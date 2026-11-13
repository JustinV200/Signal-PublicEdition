"""`vault list`: show stored credentials (id, name, origins, username hint). Decrypts nothing."""

import argparse

from vault.cli.context import CliContext
from vault.store import load_vault

NAME = "list"
HELP = "List stored credentials (no secrets; nothing is decrypted)."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """list takes no arguments."""


def run(args: argparse.Namespace, context: CliContext) -> int:
    """Print one line per credential. Returns the exit code.

    Raises:
        VaultNotInitializedError: No vault yet.
        VaultFormatError: store.json is malformed.
    """
    records = load_vault(context.store_path).records
    if not records:
        context.out("no credentials stored")
    for record in records:
        meta = record.meta
        hint = meta.username_hint or "(no username)"
        context.out(f"{meta.id}\t{meta.name}\t{' '.join(meta.origins)}\t{hint}")
    return 0
