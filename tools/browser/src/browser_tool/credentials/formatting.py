"""Turn credential results into the short texts the model sees.

fill_login's result is only "ok" or "failed: <reason>". The reason must look like
a short code (lowercase letters, digits, underscores); anything else becomes
"error", so even a buggy vault can't echo a value through the reason.
"""

import re

from browser_tool.credentials.types import CredentialInfo, FillResult

FILL_OK = "ok"
FALLBACK_REASON = "error"
NO_CREDENTIALS = "no credentials in the vault"
_SAFE_REASON = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_MAX_FIELD_CHARS = 120


def format_fill_result(result: FillResult) -> str:
    """Return "ok" or "failed: <reason code>"."""
    if result.ok:
        return FILL_OK
    return f"failed: {safe_reason(result.reason)}"


def safe_reason(reason: str) -> str:
    """Return `reason` if it is a short code, else "error"."""
    return reason if _SAFE_REASON.match(reason) else FALLBACK_REASON


def format_credentials(credentials: list[CredentialInfo]) -> str:
    """One line per credential: id, label, origins, username hint."""
    if not credentials:
        return NO_CREDENTIALS
    lines = []
    for credential in credentials:
        origins = ", ".join(_one_line(origin) for origin in credential.origins)
        lines.append(
            f"- {_one_line(credential.id)}: {_one_line(credential.label)}"
            f" | origins: {origins}"
            f" | user: {_one_line(credential.username_hint)}"
        )
    return "\n".join(lines)


def _one_line(text: str) -> str:
    flat = " ".join(text.split())
    return flat[:_MAX_FIELD_CHARS]
