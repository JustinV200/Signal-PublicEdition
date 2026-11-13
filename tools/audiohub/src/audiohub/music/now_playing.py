"""`NowPlaying`: what a music backend reports is currently loaded, in one shape for all backends."""

from dataclasses import dataclass

# Source label for tracks reported by the Spotify Web API.
SPOTIFY_SOURCE = "spotify"
# Prefix for tracks reported by a Windows media session; the app id follows it.
SMTC_SOURCE_PREFIX = "smtc:"


@dataclass(frozen=True)
class NowPlaying:
    """The current track (or episode, or video) of one player.

    Attributes:
        title: Track title. Empty if the player didn't say.
        artist: Artist names joined with ", ". Empty if unknown.
        album: Album title. Empty if unknown.
        is_playing: True while playing, False while paused or stopped.
        source: "spotify" for the Web API, or "smtc:<app id>" for a Windows
            media session (e.g. "smtc:Spotify.exe", "smtc:MSEdge").
    """

    title: str
    artist: str
    album: str
    is_playing: bool
    source: str

    def describe(self) -> str:
        """Return a speakable "Title by Artist", dropping whichever part is unknown.

        Returns:
            e.g. "Babydoll by Dominic Fike", "Babydoll", or "an unnamed track".
        """
        if self.title and self.artist:
            return f"{self.title} by {self.artist}"
        return self.title or self.artist or "an unnamed track"
