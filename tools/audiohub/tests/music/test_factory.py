"""Tests for audiohub.music.factory: `[music] backend` picks the controller."""

import dataclasses

import pytest

from audiohub.config import MusicSettings
from audiohub.music import (
    AUTO_BACKEND,
    SMTC_BACKEND,
    SPOTIFY_BACKEND,
    FallbackController,
    SmtcController,
    SpotifyController,
    create_controller,
)


@pytest.mark.parametrize(
    ("backend", "expected_type"),
    [
        (AUTO_BACKEND, FallbackController),
        (SPOTIFY_BACKEND, SpotifyController),
        (SMTC_BACKEND, SmtcController),
    ],
)
def test_backend_setting_picks_the_controller(backend, expected_type):
    settings = MusicSettings(backend=backend)
    assert isinstance(create_controller(settings), expected_type)


def test_unknown_backend_is_a_programming_error():
    # Bypasses config validation, which normally rejects this on load.
    settings = dataclasses.replace(MusicSettings(), backend="winamp")
    with pytest.raises(ValueError, match="winamp"):
        create_controller(settings)
