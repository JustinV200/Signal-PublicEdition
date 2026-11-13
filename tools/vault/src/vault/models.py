"""Public result types: everything the vault hands back to the browser tool (and the model).

Nothing in this file ever holds a secret. `CredentialInfo` carries a username
hint only, and `FillResult` carries a fixed reason code, never an exception
message (Playwright error messages contain the filled value).
"""

from dataclasses import dataclass

# FillResult.reason codes. They are fixed strings so the browser tool can show
# them to the model verbatim without leaking anything.
REASON_FILLED = "filled"
REASON_ORIGIN_MISMATCH = "origin_mismatch"
REASON_DENIED = "denied"
REASON_LOCKED = "locked"
REASON_NO_FIELDS = "no_fields"
REASON_NOT_FOUND = "not_found"
REASON_TAMPERED = "tampered"
REASON_UNSAFE_ENVIRONMENT = "unsafe_environment"
REASON_ERROR = "error"


@dataclass(frozen=True)
class CredentialInfo:
    """What the model may know about a stored credential.

    Attributes:
        id: The credential id the model passes to `fill_login`.
        name: The owner's display name for it, e.g. "GitHub".
        origins: The exact https origins it may be filled on.
        username_hint: A masked hint such as "j***@example.com", never the username.
    """

    id: str
    name: str
    origins: tuple[str, ...]
    username_hint: str


@dataclass(frozen=True)
class FillResult:
    """The outcome of `fill_login`.

    Attributes:
        ok: True only when the fields were filled (and submitted, if asked).
        reason: One of the REASON_* codes above. Never an exception message.
    """

    ok: bool
    reason: str
