"""Public API of audiohub.music.spotify: the Spotify Web API music backend.

The rest of audiohub.music imports Spotify features from here only.
"""

from audiohub.music.spotify.auth import (
    CLIENT_ID_ENV_VAR,
    SCOPES,
    TOKEN_CACHE_PATH,
    SpotifyAuth,
)
from audiohub.music.spotify.controller import SEARCH_LIMIT, SpotifyController

__all__ = [
    "CLIENT_ID_ENV_VAR",
    "SCOPES",
    "SEARCH_LIMIT",
    "TOKEN_CACHE_PATH",
    "SpotifyAuth",
    "SpotifyController",
]
