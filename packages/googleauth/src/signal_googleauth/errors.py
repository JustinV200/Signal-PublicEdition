"""GoogleAuthError and its kinds: what the shared Google sign-in code can fail with.

Messages are safe to show: they never hold a token, a client secret or an
exception chain that might. Each tool maps these onto its own error types.
"""


class GoogleAuthError(Exception):
    """Base for expected sign-in failures. str(error) is always safe to show."""


class ClientFileError(GoogleAuthError):
    """The Desktop-app OAuth client JSON is missing or invalid."""


class SignInError(GoogleAuthError):
    """The browser sign-in timed out, was cancelled, failed, or granted too few scopes."""
