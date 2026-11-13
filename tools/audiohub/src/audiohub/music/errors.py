"""Exceptions every music backend raises, with messages fit to be spoken to the user.

`MusicUnavailable` carries an `UnavailableReason`, so FallbackController can
tell "Spotify isn't set up" (try the Windows media session instead) apart from
"Spotify said no" (report it). `str(error)` is always the speakable message.
"""

from enum import StrEnum


class UnavailableReason(StrEnum):
    """Why a music backend couldn't do what was asked."""

    # Spotify: SPOTIPY_CLIENT_ID is unset.
    NOT_CONFIGURED = "not_configured"
    # Spotify: no cached token, or it was revoked/expired beyond refresh.
    NOT_LOGGED_IN = "not_logged_in"
    # Spotify: the Web API sees no Spotify Connect device (app closed or idle).
    NO_ACTIVE_DEVICE = "no_active_device"
    # Spotify: the account (or the developer app's owner) lacks Premium.
    PREMIUM_REQUIRED = "premium_required"
    # Spotify: still rate limited after spotipy's own retries.
    RATE_LIMITED = "rate_limited"
    # Spotify: a search found nothing playable.
    NOT_FOUND = "not_found"
    # Spotify: a player restriction refused the command ("Restriction
    # violated"), e.g. a private session, or pausing a paused player.
    RESTRICTED = "restricted"
    # Windows media session: no app is exposing a media session.
    NO_SESSION = "no_session"
    # Windows media session: the winrt projection can't be imported.
    BACKEND_MISSING = "backend_missing"
    # The backend was reached but refused or failed the request.
    REQUEST_FAILED = "request_failed"


class MusicUnavailable(Exception):
    """A music command couldn't be carried out right now.

    Attributes:
        message: A short sentence that can be spoken to the user as is.
        reason: The machine-readable cause.
    """

    def __init__(self, message: str, reason: UnavailableReason) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class UnsupportedOperation(Exception):
    """The backend can never do this (e.g. search through the Windows media session).

    Attributes:
        message: A short sentence that can be spoken to the user as is.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
