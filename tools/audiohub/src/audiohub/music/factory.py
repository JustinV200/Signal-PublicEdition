"""`create_controller`: build the MusicController that `[music] backend` asks for."""

from audiohub.config import MUSIC_BACKENDS, MusicSettings
from audiohub.music.controller import MusicController
from audiohub.music.fallback import FallbackController
from audiohub.music.smtc import SmtcController
from audiohub.music.spotify import SpotifyController

# The `[music] backend` values, named. Unpacked from config so the two can't
# drift apart; a backend added to MUSIC_BACKENDS fails here until handled.
AUTO_BACKEND, SPOTIFY_BACKEND, SMTC_BACKEND = MUSIC_BACKENDS


def create_controller(music_settings: MusicSettings) -> MusicController:
    """Build the configured music backend. Makes no network or Windows calls.

    Args:
        music_settings: `backend` picks the controller:
            - "auto": Spotify, falling back to the Windows media session
            - "spotify": Spotify only
            - "smtc": the Windows media session only

    Raises:
        ValueError: For any other backend (config validation prevents this).
    """
    backend = music_settings.backend
    if backend == SPOTIFY_BACKEND:
        return SpotifyController(music_settings)
    if backend == SMTC_BACKEND:
        return SmtcController()
    if backend == AUTO_BACKEND:
        return FallbackController(SpotifyController(music_settings), SmtcController())
    raise ValueError(f"unknown music backend {backend!r}")
