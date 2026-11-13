"""Turn spotipy's `SpotifyException` into a speakable `MusicUnavailable`, and log it.

Spotify's player endpoints report most problems as an HTTP status plus an
`error.reason` string; see the "Player error reasons" in the Web API docs.
A "Restriction violated" refusal the caller expects (pausing a paused
player) is logged once, at DEBUG, here; spotipy's own ERROR line for it is
dropped.
"""

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from spotipy.exceptions import SpotifyException

from audiohub.music.errors import MusicUnavailable, UnavailableReason
from audiohub.music.spotify import messages

logger = logging.getLogger(__name__)

HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429

# `error.reason` values Spotify's player endpoints send.
NO_ACTIVE_DEVICE_REASON = "NO_ACTIVE_DEVICE"
PREMIUM_REQUIRED_REASON = "PREMIUM_REQUIRED"
VOLUME_CONTROL_DISALLOW_REASON = "VOLUME_CONTROL_DISALLOW"

RESTRICTION_VIOLATED_REASON = "RESTRICTION_VIOLATED"

# Body texts (lowercase) that identify a 403 when there's no useful `reason`.
RESTRICTION_VIOLATED_TEXT = "restriction violated"
NOT_REGISTERED_TEXT = "not be registered"  # "...the user may not be registered."
INSUFFICIENT_SCOPE_TEXT = "insufficient client scope"

# Longest body excerpt logged or spoken.
MAX_DETAIL_CHARS = 120

# spotipy's own logger, which logs every HTTP error at ERROR before raising it.
SPOTIPY_LOGGER_NAME = "spotipy.client"


def to_music_unavailable(
    error: SpotifyException, *, refusal_expected: bool = False
) -> MusicUnavailable:
    """Map a spotipy HTTP error to MusicUnavailable with the most helpful message.

    Logs the status, reason and a short body excerpt (never a token) at
    WARNING, so a vague spoken message can be traced in the log.

    Args:
        error: What spotipy raised.
        refusal_expected: The caller expects a "Restriction violated" refusal
            and checks the outcome itself, so that refusal is logged at DEBUG.
            Any other error is still logged at WARNING.

    Returns:
        The exception to raise instead (the caller chains `from error`).
    """
    detail = _short_detail(error)
    unavailable = _classify(error, detail)
    is_routine = refusal_expected and unavailable.reason is UnavailableReason.RESTRICTED
    logger.log(
        logging.DEBUG if is_routine else logging.WARNING,
        "Spotify error: status=%s reason=%s body=%s",
        error.http_status,
        error.reason,
        detail,
    )
    return unavailable


@contextmanager
def spotipy_refusal_log_dropped() -> Iterator[None]:
    """While active, drop spotipy's ERROR line for a "Restriction violated" refusal.

    Only for a call whose caller expects that refusal: `to_music_unavailable`
    still logs it, at DEBUG. Only lines from the calling thread are dropped,
    so another thread's refusal and every other error stay logged.
    """
    thread_id = threading.get_ident()

    def keep(record: logging.LogRecord) -> bool:
        is_refusal = RESTRICTION_VIOLATED_TEXT in record.getMessage().lower()
        return record.thread != thread_id or not is_refusal

    spotipy_logger = logging.getLogger(SPOTIPY_LOGGER_NAME)
    spotipy_logger.addFilter(keep)
    try:
        yield
    finally:
        spotipy_logger.removeFilter(keep)


def _short_detail(error: SpotifyException) -> str:
    # spotipy formats msg as "<url>:\n <body message>"; keep only the body part.
    text = str(error.msg or "").split("\n")[-1].strip()
    return text[:MAX_DETAIL_CHARS]


def _classify(error: SpotifyException, detail: str) -> MusicUnavailable:
    status = error.http_status
    reason = error.reason or ""
    body = str(error.msg or "").lower()
    if reason == NO_ACTIVE_DEVICE_REASON or status == HTTP_NOT_FOUND:
        # Player endpoints only 404 when there's no Spotify Connect device to command.
        return MusicUnavailable(messages.NO_ACTIVE_DEVICE, UnavailableReason.NO_ACTIVE_DEVICE)
    if reason == PREMIUM_REQUIRED_REASON:
        return MusicUnavailable(messages.PREMIUM_REQUIRED, UnavailableReason.PREMIUM_REQUIRED)
    if reason == VOLUME_CONTROL_DISALLOW_REASON:
        return MusicUnavailable(messages.VOLUME_DISALLOWED, UnavailableReason.REQUEST_FAILED)
    if status == HTTP_UNAUTHORIZED or INSUFFICIENT_SCOPE_TEXT in body:
        return MusicUnavailable(messages.MISSING_SCOPE, UnavailableReason.NOT_LOGGED_IN)
    if NOT_REGISTERED_TEXT in body:
        return MusicUnavailable(messages.USER_NOT_REGISTERED, UnavailableReason.REQUEST_FAILED)
    if reason == RESTRICTION_VIOLATED_REASON or RESTRICTION_VIOLATED_TEXT in body:
        return MusicUnavailable(messages.RESTRICTED, UnavailableReason.RESTRICTED)
    if status == HTTP_TOO_MANY_REQUESTS:
        return MusicUnavailable(messages.RATE_LIMITED, UnavailableReason.RATE_LIMITED)
    return MusicUnavailable(
        messages.request_failed(status, reason or detail), UnavailableReason.REQUEST_FAILED
    )
