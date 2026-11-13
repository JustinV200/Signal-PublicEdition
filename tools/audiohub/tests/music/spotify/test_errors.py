"""Tests for audiohub.music.spotify.errors: spotipy HTTP errors become speakable messages."""

import logging

import pytest
from spotipy.exceptions import SpotifyException

from audiohub.music import UnavailableReason
from audiohub.music.spotify.errors import to_music_unavailable


def spotify_error(status: int, reason: str | None = None, msg: str = "") -> SpotifyException:
    return SpotifyException(status, -1, msg, reason=reason)


@pytest.mark.parametrize(
    ("error", "expected_reason", "message_part"),
    [
        (
            spotify_error(404, "NO_ACTIVE_DEVICE"),
            UnavailableReason.NO_ACTIVE_DEVICE,
            "open the Spotify app",
        ),
        (spotify_error(404), UnavailableReason.NO_ACTIVE_DEVICE, "any device"),
        (spotify_error(403, "PREMIUM_REQUIRED"), UnavailableReason.PREMIUM_REQUIRED, "Premium"),
        (
            spotify_error(403, None, "Check settings, the user may not be registered."),
            UnavailableReason.REQUEST_FAILED,
            "user list",
        ),
        (
            spotify_error(403, "UNKNOWN", "Player command failed: Restriction violated"),
            UnavailableReason.RESTRICTED,
            "private session",
        ),
        (
            spotify_error(403, "RESTRICTION_VIOLATED"),
            UnavailableReason.RESTRICTED,
            "private session",
        ),
        (
            spotify_error(403, "VOLUME_CONTROL_DISALLOW"),
            UnavailableReason.REQUEST_FAILED,
            "volume",
        ),
        (spotify_error(401), UnavailableReason.NOT_LOGGED_IN, "missing a permission"),
        (
            spotify_error(403, None, "Insufficient client scope"),
            UnavailableReason.NOT_LOGGED_IN,
            "missing a permission",
        ),
        (spotify_error(429), UnavailableReason.RATE_LIMITED, "limiting"),
        (spotify_error(502), UnavailableReason.REQUEST_FAILED, "Spotify error 502"),
        (
            spotify_error(403, "UNKNOWN", "x:\n Something odd"),
            UnavailableReason.REQUEST_FAILED,
            "Spotify error 403: UNKNOWN",
        ),
    ],
)
def test_spotify_errors_map_to_speakable_reasons(error, expected_reason, message_part):
    mapped = to_music_unavailable(error)
    assert mapped.reason is expected_reason
    assert message_part in str(mapped)


def test_a_bare_403_is_not_blamed_on_premium_or_the_user_list():
    mapped = to_music_unavailable(spotify_error(403))
    assert str(mapped) == "Spotify error 403"
    assert mapped.reason is not UnavailableReason.PREMIUM_REQUIRED


@pytest.mark.parametrize("refusal_expected", [False, True])
def test_every_error_is_logged_with_status_reason_and_body(caplog, refusal_expected):
    # Not a restriction, so it's a WARNING even when the caller expects a refusal.
    error = spotify_error(403, "UNKNOWN", "https://api.spotify.com/v1/me/player/play:\n Nope")
    with caplog.at_level(logging.WARNING, logger="audiohub.music.spotify.errors"):
        to_music_unavailable(error, refusal_expected=refusal_expected)
    (record,) = caplog.records
    assert record.levelno == logging.WARNING
    assert "status=403" in record.getMessage()
    assert "reason=UNKNOWN" in record.getMessage()
    assert "body=Nope" in record.getMessage()
