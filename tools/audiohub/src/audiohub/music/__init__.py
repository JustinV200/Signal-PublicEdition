"""Public API of audiohub.music: music control through Spotify or the Windows media session.

Other packages (cli, mcp, loop) import music features from here only. This
package imports nothing from audiohub except audiohub.config.

The Spotify side (spotipy, requests, redis: ~0.2 s) loads on first use of a
name that needs it, so `audiohub` commands that never touch music skip it.
"""

import importlib
from typing import TYPE_CHECKING, Any

from audiohub.music.arguments import (
    MAX_VOLUME_PERCENT,
    MIN_VOLUME_PERCENT,
    check_query,
    check_search_kind,
    check_volume_percent,
)
from audiohub.music.controller import SEARCH_KINDS, MusicController, SearchKind
from audiohub.music.errors import MusicUnavailable, UnavailableReason, UnsupportedOperation
from audiohub.music.fallback import FALLBACK_REASONS, FallbackController
from audiohub.music.now_playing import NowPlaying
from audiohub.music.smtc import SmtcController

if TYPE_CHECKING:
    from audiohub.music.factory import (
        AUTO_BACKEND,
        SMTC_BACKEND,
        SPOTIFY_BACKEND,
        create_controller,
    )
    from audiohub.music.spotify import CLIENT_ID_ENV_VAR, TOKEN_CACHE_PATH, SpotifyController

# Lazily loaded name -> the module that defines it.
_LAZY = {
    "AUTO_BACKEND": "audiohub.music.factory",
    "SMTC_BACKEND": "audiohub.music.factory",
    "SPOTIFY_BACKEND": "audiohub.music.factory",
    "create_controller": "audiohub.music.factory",
    "CLIENT_ID_ENV_VAR": "audiohub.music.spotify",
    "TOKEN_CACHE_PATH": "audiohub.music.spotify",
    "SpotifyController": "audiohub.music.spotify",
}


def __getattr__(name: str) -> Any:
    """Import a Spotify-side name on first access (PEP 562)."""
    if name not in _LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(_LAZY[name]), name)


__all__ = [
    "AUTO_BACKEND",
    "CLIENT_ID_ENV_VAR",
    "FALLBACK_REASONS",
    "MAX_VOLUME_PERCENT",
    "MIN_VOLUME_PERCENT",
    "SEARCH_KINDS",
    "SMTC_BACKEND",
    "SPOTIFY_BACKEND",
    "TOKEN_CACHE_PATH",
    "FallbackController",
    "MusicController",
    "MusicUnavailable",
    "NowPlaying",
    "SearchKind",
    "SmtcController",
    "SpotifyController",
    "UnavailableReason",
    "UnsupportedOperation",
    "check_query",
    "check_search_kind",
    "check_volume_percent",
    "create_controller",
]
