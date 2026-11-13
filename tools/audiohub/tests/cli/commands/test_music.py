"""Tests for the `audiohub music ...` command, with the music backends replaced by fakes."""

from pathlib import Path

import pytest

import audiohub.music as music_api
from audiohub.cli import main
from audiohub.cli.main import build_parser
from audiohub.config import loader
from audiohub.music import (
    CLIENT_ID_ENV_VAR,
    MusicUnavailable,
    NowPlaying,
    UnavailableReason,
    UnsupportedOperation,
)

EDGE_TRACK = NowPlaying("Babydoll", "Dominic Fike", "", False, "smtc:MSEdge")


class RecordingMusic:
    """A MusicController fake: records calls, optionally raises `error` from every one."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple] = []
        self.error = error

    async def _record(self, *call: object) -> None:
        self.calls.append(call)
        if self.error is not None:
            raise self.error

    async def play(self):
        await self._record("play")

    async def pause(self):
        await self._record("pause")

    async def toggle(self):
        await self._record("toggle")

    async def next(self):
        await self._record("next")

    async def previous(self):
        await self._record("previous")

    async def now_playing(self):
        await self._record("now_playing")
        return EDGE_TRACK

    async def set_volume(self, percent):
        await self._record("set_volume", percent)

    async def search_and_play(self, query, kind="track"):
        await self._record("search_and_play", query, kind)
        return "Babydoll by Dominic Fike"

    async def queue(self, query):
        await self._record("queue", query)
        return "Babydoll by Dominic Fike"


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    # Keep a real audiohub.toml or SPOTIPY_CLIENT_ID from changing these tests.
    monkeypatch.setattr(loader, "DEFAULT_CONFIG_PATH", tmp_path / "absent.toml")
    monkeypatch.delenv(CLIENT_ID_ENV_VAR, raising=False)


@pytest.fixture
def fake_music(monkeypatch) -> RecordingMusic:
    music = RecordingMusic()
    monkeypatch.setattr(music_api, "create_controller", lambda _settings: music)
    return music


@pytest.mark.parametrize("value", ["150", "-1", "loud"])
def test_bad_volume_is_a_usage_error(value):
    with pytest.raises(SystemExit):
        build_parser().parse_args(["music", "volume", value])


@pytest.mark.parametrize(
    ("action", "call", "printed"),
    [
        ("pause", "pause", "Paused."),
        ("prev", "previous", "Went back."),
        ("next", "next", "Skipped."),
    ],
)
def test_simple_actions_call_the_controller(fake_music, capsys, action, call, printed):
    assert main(["music", action]) == 0
    assert fake_music.calls == [(call,)]
    assert capsys.readouterr().out.strip() == printed


def test_volume_play_search_and_queue(fake_music, capsys):
    assert main(["music", "volume", "40"]) == 0
    assert main(["music", "play-search", "babydoll", "--kind", "track"]) == 0
    assert main(["music", "queue", "babydoll", "dominic"]) == 0
    assert fake_music.calls == [
        ("set_volume", 40),
        ("search_and_play", "babydoll", "track"),
        ("queue", "babydoll dominic"),
    ]
    output = capsys.readouterr().out
    assert "Volume set to 40%." in output
    assert "Playing Babydoll by Dominic Fike." in output
    assert "Queued Babydoll by Dominic Fike." in output


@pytest.mark.parametrize(
    "error",
    [
        MusicUnavailable("Open the Spotify app.", UnavailableReason.NO_ACTIVE_DEVICE),
        UnsupportedOperation("I can't do that."),
    ],
)
def test_backend_refusals_print_the_reason_and_exit_1(monkeypatch, capsys, error):
    monkeypatch.setattr(music_api, "create_controller", lambda _s: RecordingMusic(error))
    assert main(["music", "play"]) == 1
    assert capsys.readouterr().err.strip() == f"audiohub: music: {error}"


def test_status_shows_spotify_not_configured_and_the_fallback_track(fake_music, capsys):
    assert main(["music", "status"]) == 0
    output = capsys.readouterr().out
    assert "Backend:     auto" in output
    assert "Spotify:     not configured: Spotify isn't set up." in output
    assert "Now playing: Babydoll by Dominic Fike [paused] from smtc:MSEdge" in output


def test_status_with_smtc_backend_skips_spotify(fake_music, tmp_path, capsys):
    config = tmp_path / "music.toml"
    config.write_text("[music]\nbackend = 'smtc'\n", encoding="utf-8")
    assert main(["music", "status", "--config", str(config)]) == 0
    assert "Spotify:" not in capsys.readouterr().out


def test_status_reports_an_unknown_track(monkeypatch, capsys):
    error = MusicUnavailable("Nothing is playing.", UnavailableReason.NO_SESSION)
    monkeypatch.setattr(music_api, "create_controller", lambda _s: RecordingMusic(error))
    assert main(["music", "status"]) == 0
    assert "Now playing: unknown (Nothing is playing.)" in capsys.readouterr().out


def test_login_without_client_id_fails_before_opening_a_browser(capsys):
    assert main(["music", "login"]) == 1
    captured = capsys.readouterr()
    assert "SPOTIPY_CLIENT_ID" in captured.err
    assert "Opening your browser" not in captured.out


def test_login_runs_the_browser_flow(monkeypatch, capsys):
    class FakeSpotify:
        def __init__(self, _settings):
            pass

        def check_ready(self):
            raise MusicUnavailable("not yet", UnavailableReason.NOT_LOGGED_IN)

        def login(self):
            return Path("token.json")

    monkeypatch.setattr(music_api, "SpotifyController", FakeSpotify)
    assert main(["music", "login"]) == 0
    output = capsys.readouterr().out
    assert "Opening your browser" in output
    assert "Logged in to Spotify. Token cached at token.json" in output
