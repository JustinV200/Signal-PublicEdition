"""Choose which Windows media session to control: Spotify's if it has one, else the current one.

Listing every session needs the `winrt-Windows.Foundation.Collections`
projection (a pinned dependency). If it's ever missing, `get_sessions()`
raises ModuleNotFoundError; we then log a warning once and use the session
Windows considers current.
"""

import functools
import logging

from audiohub.music.smtc.manager import MediaSession, SessionManager

logger = logging.getLogger(__name__)

# Case-insensitive text in Spotify's app id, for both the classic installer
# ("Spotify.exe") and the Microsoft Store build ("SpotifyAB.SpotifyMusic_...").
SPOTIFY_APP_ID_TEXT = "spotify"

# The projection module get_sessions() needs for its IVectorView result.
COLLECTIONS_MODULE = "winrt.windows.foundation.collections"


def pick_session(manager: SessionManager) -> MediaSession | None:
    """Return Spotify's media session if there is one, otherwise the current session.

    Returns:
        The session, or None when no app is exposing a media session.
    """
    for session in list_sessions(manager):
        if SPOTIFY_APP_ID_TEXT in session.source_app_user_model_id.lower():
            return session
    return manager.get_current_session()


def list_sessions(manager: SessionManager) -> list[MediaSession]:
    """Return every media session, or [] if the collections projection isn't installed.

    Raises:
        ModuleNotFoundError: For any missing module other than the collections projection.
    """
    try:
        return list(manager.get_sessions())
    except ModuleNotFoundError as error:
        if error.name != COLLECTIONS_MODULE:
            raise
        _warn_sessions_unlisted()
        return []


@functools.cache
def _warn_sessions_unlisted() -> None:
    # Cached so the warning is logged once per process, not on every command.
    logger.warning(
        "%s isn't installed, so Spotify's media session can't be picked out; "
        "using the current media session instead",
        COLLECTIONS_MODULE,
    )
