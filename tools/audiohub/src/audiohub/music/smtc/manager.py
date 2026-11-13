"""The winrt boundary for the Windows media session (SMTC): the manager request and its errors.

The winrt import is deferred to the first call, so audiohub still loads (and
the Spotify backend still works) where the winrt wheels are missing. winrt
reports failed HRESULTs as OSError; `winrt_errors_as_unavailable` turns those
into a speakable MusicUnavailable so they never escape as a traceback.
"""

import contextlib
from collections.abc import Iterator
from typing import Any, Protocol

from audiohub.music.errors import MusicUnavailable, UnavailableReason

BACKEND_MISSING_MESSAGE = "The Windows media controls aren't available on this PC."
NOT_RESPONDING_MESSAGE = "The Windows media controls aren't responding."


class MediaSession(Protocol):
    """The part of winrt's GlobalSystemMediaTransportControlsSession that audiohub uses.

    The try_*_async methods return winrt IAsyncOperation objects, which are awaitable.
    """

    @property
    def source_app_user_model_id(self) -> str: ...
    def get_playback_info(self) -> Any: ...
    def try_get_media_properties_async(self) -> Any: ...
    def try_play_async(self) -> Any: ...
    def try_pause_async(self) -> Any: ...
    def try_toggle_play_pause_async(self) -> Any: ...
    def try_skip_next_async(self) -> Any: ...
    def try_skip_previous_async(self) -> Any: ...


class SessionManager(Protocol):
    """The part of winrt's GlobalSystemMediaTransportControlsSessionManager audiohub uses."""

    def get_current_session(self) -> MediaSession | None: ...
    def get_sessions(self) -> Any: ...


@contextlib.contextmanager
def winrt_errors_as_unavailable(message: str = NOT_RESPONDING_MESSAGE) -> Iterator[None]:
    """Re-raise an OSError from winrt inside the block as MusicUnavailable(REQUEST_FAILED).

    Args:
        message: The speakable message to raise with.

    Raises:
        MusicUnavailable: REQUEST_FAILED, chained from the OSError.
    """
    try:
        yield
    except OSError as error:
        raise MusicUnavailable(message, UnavailableReason.REQUEST_FAILED) from error


async def request_session_manager() -> SessionManager:
    """Ask Windows for the media session manager.

    Raises:
        MusicUnavailable: BACKEND_MISSING if winrt can't be imported, or
            REQUEST_FAILED if Windows refuses the request.
    """
    try:
        # Deferred import: see the module docstring.
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as WinrtSessionManager,
        )
    except ImportError as error:
        reason = UnavailableReason.BACKEND_MISSING
        raise MusicUnavailable(BACKEND_MISSING_MESSAGE, reason) from error
    with winrt_errors_as_unavailable():
        return await WinrtSessionManager.request_async()
