"""`vault policy ID --confirm always|never`: choose whether fills show the Allow/Deny dialog.

The policy is bound into each record's ciphertext, so changing it re-keys the
whole vault (a fresh data key, like `vault remove`): an old copy of the record,
sealed under the previous policy, stops decrypting. Editing store.json by hand
just breaks the record. "never" leaves the unlock (Hello) as the only gate.
"""

import argparse
import asyncio
import dataclasses

from vault.audit import EVENT_POLICY
from vault.cli.context import CliContext
from vault.cli.terminal import CliError, require_interactive_stdin
from vault.crypto import DecryptionError
from vault.store import (
    POLICY_CONFIRM_ALWAYS,
    POLICY_CONFIRM_KEY,
    POLICY_CONFIRM_NEVER,
    CredentialMeta,
    TamperedRecordError,
    load_vault,
    rotate_records,
    save_vault,
)
from vault.unlock import UnlockError

NAME = "policy"
HELP = "Set whether fills of a credential ask first (always) or skip the dialog (never)."
CHOICES = (POLICY_CONFIRM_ALWAYS, POLICY_CONFIRM_NEVER)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add policy's arguments."""
    parser.add_argument("id", help="The credential id.")
    parser.add_argument("--confirm", required=True, choices=CHOICES, help="Dialog on each fill.")


def run(args: argparse.Namespace, context: CliContext) -> int:
    """Set the policy and rotate the data key. Returns the exit code.

    Raises:
        CliError: Not a terminal, no such credential, or the vault didn't unlock or verify.
    """
    require_interactive_stdin(context.stdin)
    data = load_vault(context.store_path)
    record = data.find(args.id)
    if record is None:
        raise CliError(f"no credential named {args.id!r}")
    old = record.meta.policy.get(POLICY_CONFIRM_KEY, POLICY_CONFIRM_ALWAYS)

    def edit(meta: CredentialMeta) -> CredentialMeta:
        if meta.id != args.id:
            return meta
        return dataclasses.replace(meta, policy={**meta.policy, POLICY_CONFIRM_KEY: args.confirm})

    unlocker = context.unlocker_for(data.header.provider)
    try:
        rotated = asyncio.run(rotate_records(data, data.records, unlocker, edit))
    except (UnlockError, DecryptionError, TamperedRecordError):
        raise CliError("could not unlock or verify the vault; nothing was changed") from None
    save_vault(context.store_path, rotated)
    context.audit.record(EVENT_POLICY, args.id, f"confirm={args.confirm}")
    context.out(f"{args.id}: confirm {old} -> {args.confirm}")
    return 0
