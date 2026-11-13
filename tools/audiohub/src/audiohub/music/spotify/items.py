"""Read Spotify Web API objects: artist names, speakable descriptions, and search matches.

Responses come from the network, so every field is read defensively: a
missing or odd-shaped field becomes an empty string, never a KeyError.
"""

from dataclasses import dataclass
from typing import Any

from audiohub.music.controller import SearchKind


@dataclass(frozen=True)
class SearchMatch:
    """The search result chosen to play or queue.

    Attributes:
        uri: Its Spotify URI, e.g. "spotify:track:...".
        kind: What was searched for.
        description: Speakable, e.g. "the album Sunburn by Dominic Fike".
    """

    uri: str
    kind: SearchKind
    description: str


def artist_names(item: dict[str, Any]) -> str:
    """Return the item's artist names joined with ", ", or "" if it has none."""
    artists = item.get("artists")
    if not isinstance(artists, list):
        return ""
    names = [artist.get("name") for artist in artists if isinstance(artist, dict)]
    return ", ".join(name for name in names if isinstance(name, str) and name)


def describe_item(item: dict[str, Any], kind: SearchKind) -> str:
    """Return a speakable description of a track, album, playlist or artist object."""
    name = item.get("name") or "something"
    artists = artist_names(item)
    if kind == "track":
        return f"{name} by {artists}" if artists else name
    if kind == "album":
        return f"the album {name} by {artists}" if artists else f"the album {name}"
    if kind == "playlist":
        return f"the playlist {name}"
    return f"songs by {name}"


def _name_fit(item: dict[str, Any], query_words: set[str]) -> int:
    """Return how many words of the item's name the query spells out, or 0 unless all of them."""
    words = str(item.get("name") or "").lower().split()
    return len(words) if words and all(word in query_words for word in words) else 0


def first_match(results: dict[str, Any], kind: SearchKind, query: str = "") -> SearchMatch | None:
    """Return the best usable item in a `GET /search` response, or None.

    Prefers the item whose whole name appears in the query (longest name wins),
    so "Attention Joji" picks "ATTENTION" over a louder unrelated hit. Falls
    back to the first usable item.

    Args:
        results: The search response. Items sit under "<kind>s" -> "items".
        kind: The kind that was searched for.
        query: What the user asked for; empty means just take the first item.
    """
    section = results.get(f"{kind}s")
    items = section.get("items") if isinstance(section, dict) else None
    # Playlist searches can contain null entries, so skip anything without a URI.
    usable = [i for i in items or [] if isinstance(i, dict) and isinstance(i.get("uri"), str)]
    if not usable:
        return None
    query_words = set(query.lower().split())
    # max() keeps the earliest item on ties, so no fit at all means the first result.
    best = max(usable, key=lambda item: _name_fit(item, query_words))
    return SearchMatch(uri=best["uri"], kind=kind, description=describe_item(best, kind))


def liked_songs_uri(profile: dict[str, Any]) -> str | None:
    """Return the context URI of the user's Liked Songs, or None if `profile` has no user id.

    Liked Songs is the saved-tracks collection, not a playlist: search never
    returns it (a search finds strangers' playlists named "Liked Songs"), and
    only this per-user URI plays it as a context. Playing it needs no library
    scope, and `GET /me` gives the id with any token.

    Args:
        profile: The `GET /me` response.
    """
    user_id = profile.get("id")
    if not isinstance(user_id, str) or not user_id:
        return None
    return f"spotify:user:{user_id}:collection"
