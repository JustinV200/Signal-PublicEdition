"""load_client_config: read and check the Desktop-app OAuth client JSON the owner downloaded.

The mail and calendar tools share one client file (tools/mail/.state/google_client.json).
Error messages name the file and what's wrong with it, but never echo its
contents, since it holds the client secret.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from signal_googleauth.errors import ClientFileError

# A tampered token_uri would receive every refresh token, so only Google's are accepted.
GOOGLE_TOKEN_URI_PREFIXES = ("https://oauth2.googleapis.com/", "https://accounts.google.com/")
REQUIRED_FIELDS = ("client_id", "client_secret", "auth_uri", "token_uri")


@dataclass(frozen=True)
class ClientConfig:
    """The parts of the client JSON the tools use. repr() leaves out the secret."""

    client_id: str
    client_secret: str = field(repr=False)
    token_uri: str
    project_id: str


def load_client_config(path: Path) -> ClientConfig:
    """Read and validate the OAuth client JSON.

    Args:
        path: The client file.

    Returns:
        The client settings.

    Raises:
        ClientFileError: Missing, unreadable, not JSON, a non-Desktop client, or missing fields.
    """
    if not path.is_file():
        raise ClientFileError(
            f"No OAuth client file at {path}. Follow tools/mail/SETUP.md, step 3."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        raise ClientFileError(f"{path} isn't a readable JSON file; download it again.") from None
    if not isinstance(data, dict):
        raise ClientFileError(f"{path} isn't a Google OAuth client file.")
    if "installed" not in data:
        kind = "a Web application client" if "web" in data else "not an OAuth client file"
        raise ClientFileError(f"{path} is {kind}. Create an OAuth client ID of type Desktop app.")
    return _from_installed(data["installed"], path)


def _from_installed(section: object, path: Path) -> ClientConfig:
    """Check the "installed" section's fields and build the config."""
    if not isinstance(section, dict):
        raise ClientFileError(f"{path}: the 'installed' section isn't an object.")
    missing = [name for name in REQUIRED_FIELDS if not isinstance(section.get(name), str)]
    if missing:
        raise ClientFileError(f"{path} is missing {', '.join(missing)}; download it again.")
    if not section["token_uri"].startswith(GOOGLE_TOKEN_URI_PREFIXES):
        raise ClientFileError(f"{path}: token_uri isn't a Google address; download it again.")
    return ClientConfig(
        client_id=section["client_id"],
        client_secret=section["client_secret"],
        token_uri=section["token_uri"],
        project_id=str(section.get("project_id", "")),
    )
