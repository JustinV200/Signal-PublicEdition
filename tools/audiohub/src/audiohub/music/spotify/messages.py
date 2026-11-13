"""Speakable messages for every way a Spotify request can fail.

Kept in one place so auth, error mapping and the controller say the same
thing for the same problem. Each is a short sentence Claude can read aloud.
"""

NOT_CONFIGURED = (
    "Spotify isn't set up. Set the SPOTIPY_CLIENT_ID environment variable "
    "to your Spotify app's client ID."
)
NOT_LOGGED_IN = "Spotify isn't logged in yet. Run audiohub music login."
LOGIN_EXPIRED = "The Spotify login has expired. Run audiohub music login again."
NO_ACTIVE_DEVICE = "Spotify isn't playing on any device; open the Spotify app"
PREMIUM_REQUIRED = "Spotify needs a Premium account to control playback."
USER_NOT_REGISTERED = (
    "This Spotify account isn't on the developer app's user list. "
    "Add it under User Management in the Spotify developer dashboard."
)
MISSING_SCOPE = (
    "The Spotify login is missing a permission or has expired. Run audiohub music login again."
)
RESTRICTED = (
    "Spotify says playback is restricted right now, for example in a private "
    "session or on a device that doesn't allow that."
)
VOLUME_DISALLOWED = "The Spotify device that's playing doesn't allow volume control."
RATE_LIMITED = "Spotify is limiting requests right now. Try again in a minute."
UNREACHABLE = "I couldn't reach Spotify. Check the internet connection."
NO_USER_ID = "Spotify didn't say which account is logged in, so I can't find your Liked Songs."


def request_failed(http_status: int, detail: str) -> str:
    """Message for an HTTP error with no more specific explanation.

    Args:
        http_status: The status code Spotify returned.
        detail: A short reason from Spotify (may be empty).
    """
    suffix = f": {detail}" if detail else ""
    return f"Spotify error {http_status}{suffix}"


def pause_ignored() -> str:
    """Message for a pause Spotify accepted but that didn't stop the music."""
    return "Spotify accepted the pause, but music is still playing."


def login_failed(detail: str) -> str:
    """Message for an interactive login that didn't complete.

    Args:
        detail: What spotipy or the OS reported.
    """
    return f"The Spotify login didn't complete: {detail}"


def nothing_found(kind: str, query: str) -> str:
    """Message for a search that found nothing playable.

    Args:
        kind: The search kind, e.g. "track".
        query: What was searched for.
    """
    return f"I couldn't find a {kind} called {query} on Spotify."
