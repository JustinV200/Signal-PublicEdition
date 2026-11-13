"""Turn a Spotify `GET /me/player` response into `NowPlaying`."""

from typing import Any

from audiohub.music.now_playing import SPOTIFY_SOURCE, NowPlaying
from audiohub.music.spotify.items import artist_names


def parse_playback(playback: dict[str, Any]) -> NowPlaying | None:
    """Read the current item out of a playback-state response.

    Args:
        playback: The response body. spotipy returns None instead when no
            device is active; callers handle that before calling this.

    Returns:
        The current track, or None if the device has nothing loaded (or is
        playing something without track details, such as an ad).
    """
    item = playback.get("item")
    if not isinstance(item, dict):
        return None
    album = item.get("album")
    album_name = album.get("name") if isinstance(album, dict) else None
    return NowPlaying(
        title=item.get("name") or "",
        artist=artist_names(item),
        album=album_name or "",
        is_playing=bool(playback.get("is_playing")),
        source=SPOTIFY_SOURCE,
    )
