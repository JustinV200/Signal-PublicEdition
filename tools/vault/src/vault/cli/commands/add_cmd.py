"""`vault add ID --name N --origin URL [--origin URL ...]`: store one login.

Owner-only. Refuses non-interactive stdin before anything else, warns about
excluded account categories, reads the username and password twice with
getpass (hidden), then unlocks the vault to seal them. Prints only "added ID".
"""

import argparse
import asyncio

from vault.audit import EVENT_ADD
from vault.cli.context import CliContext
from vault.cli.exclusions import excluded_category
from vault.cli.terminal import CliError, read_hidden_twice, require_interactive_stdin
from vault.crypto import DecryptionError
from vault.origin import OriginError, origin_of_url, parse_registered_origin
from vault.store import (
    CREDENTIAL_ID_PATTERN,
    DEFAULT_POLICY,
    MAX_NAME_CHARS,
    CredentialMeta,
    CredentialRecord,
    VaultHeader,
    load_vault,
    save_vault,
    seal_credential,
    unlocked_dek,
    username_hint,
)
from vault.unlock import UnlockError

NAME = "add"
HELP = "Store a login (asks for the password, hidden, and the username unless --username)."
RESULT_OK = "ok"
CONFIRM_WORD = "yes"
EXIT_CANCELLED = 1


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add add's arguments."""
    parser.add_argument("id", help="Short id the agent will use, e.g. github (a-z, 0-9, _ and -).")
    parser.add_argument("--name", required=True, help='Display name, e.g. "GitHub".')
    parser.add_argument("--username", help="Username (not secret); skips the username prompt.")
    parser.add_argument(
        "--origin", required=True, action="append", help="An exact https origin; repeat for more."
    )


def _origin_from_input(text: str, context: CliContext) -> str:
    """A bare origin as-is; a full https URL is cut down to its origin, saying so."""
    try:
        return parse_registered_origin(text)
    except OriginError:
        origin = origin_of_url(text.strip())  # same rules; raises if the URL is bad
    context.out(f"using origin {origin}")
    return origin


def _validated_meta_fields(
    args: argparse.Namespace, context: CliContext
) -> tuple[str, str, tuple[str, ...]]:
    """Check id, name and origins; return them canonicalised."""
    if not CREDENTIAL_ID_PATTERN.match(args.id):
        raise CliError("id must be 1-64 chars of a-z, 0-9, _ or -, starting with a letter or digit")
    name = args.name.strip()
    if not 0 < len(name) <= MAX_NAME_CHARS:
        raise CliError(f"name must be 1-{MAX_NAME_CHARS} characters")
    try:
        origins = tuple(
            dict.fromkeys(_origin_from_input(origin, context) for origin in args.origin)
        )
    except OriginError as error:
        raise CliError(f"bad --origin: {error}") from None
    return args.id, name, origins


def _owner_accepts_category(
    context: CliContext, credential_id: str, name: str, origins: tuple[str, ...]
) -> bool:
    """Warn if this looks like an excluded category; True if it doesn't, or the owner insists."""
    category = excluded_category(credential_id, name, origins)
    if category is None:
        return True
    context.out(
        f"WARNING: this looks like an excluded kind of account ({category}). Those stay out: "
        "they can reset or drain other accounts, and an agent logged in there can do the same."
    )
    return context.ask_line(f"Type '{CONFIRM_WORD}' to store it anyway: ").strip() == CONFIRM_WORD


async def _seal(
    context: CliContext, header: VaultHeader, meta: CredentialMeta, username: str, password: str
) -> CredentialRecord:
    """Unlock the vault (owner prompt) and seal the login under its data key."""
    async with unlocked_dek(header, context.unlocker_for(header.provider)) as dek:
        return seal_credential(dek, header, meta, username, password)


def run(args: argparse.Namespace, context: CliContext) -> int:
    """Store the login. Returns the exit code.

    Raises:
        CliError: Not a terminal, invalid input, duplicate id, or unlock failed.
    """
    require_interactive_stdin(context.stdin)
    credential_id, name, origins = _validated_meta_fields(args, context)
    data = load_vault(context.store_path)
    if data.find(credential_id) is not None:
        raise CliError(f"{credential_id} already exists; remove it first to replace it")
    if not _owner_accepts_category(context, credential_id, name, origins):
        context.out("not added")
        return EXIT_CANCELLED
    if args.username is None:
        username = read_hidden_twice(context.read_secret, "Username", allow_empty=True)
    else:
        username = args.username
    password = read_hidden_twice(context.read_secret, "Password", allow_empty=False)
    meta = CredentialMeta(
        credential_id, name, origins, username_hint(username), dict(DEFAULT_POLICY)
    )
    try:
        record = asyncio.run(_seal(context, data.header, meta, username, password))
    except (UnlockError, DecryptionError):
        raise CliError("could not unlock the vault; nothing was added") from None
    finally:
        del username, password
    save_vault(context.store_path, data.with_record(record))
    context.audit.record(EVENT_ADD, credential_id, RESULT_OK)
    context.out(f"added {credential_id}")
    return 0
