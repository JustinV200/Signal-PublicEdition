"""Tests for audiohub.audio.ducking.ducker: Ducker logic with pycaw mocked out.

`find_sessions` and `com_initialized` are replaced so no Windows audio is
touched, time.sleep is stubbed so fades run instantly, and the crash-safety
state file lives in a temp directory. Sessions are keyed by app id, so a
restarted app is a new FakeVolume under the same app id.
"""

import contextlib
import json
import threading

import pytest

from audiohub.audio import Ducker
from audiohub.audio.ducking import ducker as ducking_module
from audiohub.audio.ducking import fade as fade_module
from audiohub.audio.ducking.sessions import AppSession
from audiohub.config import DuckingSettings

SPOTIFY = "Spotify.exe"


class FakeVolume:
    """Stands in for ISimpleAudioVolume; can be told to fail on given set calls."""

    def __init__(self, level: float, failing_calls: set[int] | None = None) -> None:
        self.level = level
        self.calls = 0
        self._failing_calls = failing_calls or set()

    def GetMasterVolume(self) -> float:  # noqa: N802 - mirrors the COM method
        return self.level

    def SetMasterVolume(self, level: float, event_context: object) -> None:  # noqa: N802
        self.calls += 1
        if self.calls in self._failing_calls:
            raise OSError("simulated COM failure")
        self.level = level


class FakeAudio:
    """The sessions find_sessions reports; tests edit it between calls."""

    def __init__(self) -> None:
        self.sessions: list[AppSession] = []
        self.lookup_error: Exception | None = None

    def add(self, volume: FakeVolume, process: str = SPOTIFY) -> FakeVolume:
        # The app id is the process name here; on Windows it also has no PID.
        self.sessions.append(AppSession(process, process, 1000, volume))
        return volume

    def restart_app(self, level: float) -> FakeVolume:
        """Replace every session with a new one, as when Spotify restarts."""
        self.sessions.clear()
        return self.add(FakeVolume(level))

    def find_sessions(self, process_names) -> list[AppSession]:
        if self.lookup_error is not None:
            raise self.lookup_error
        wanted = {name.casefold() for name in process_names}
        return [s for s in self.sessions if s.process_name.casefold() in wanted]


@pytest.fixture
def audio(monkeypatch: pytest.MonkeyPatch) -> FakeAudio:
    fake = FakeAudio()
    monkeypatch.setattr(ducking_module, "find_sessions", fake.find_sessions)
    monkeypatch.setattr(ducking_module, "com_initialized", contextlib.nullcontext)
    monkeypatch.setattr(fade_module.time, "sleep", lambda seconds: None)
    return fake


@pytest.fixture
def state_path(tmp_path):
    return tmp_path / "cache" / "ducking.json"


@pytest.fixture
def make_ducker(state_path):
    def build(**overrides) -> Ducker:
        settings = DuckingSettings(**{"level": 0.25, "fade_ms": 50, **overrides})
        return Ducker(settings, state_path=state_path)

    return build


def test_duck_then_restore_puts_back_the_exact_volume(audio, make_ducker, state_path):
    volume = audio.add(FakeVolume(0.8))
    ducker = make_ducker()
    ducker.duck()
    assert volume.level == pytest.approx(0.2)
    ducker.duck()  # ducking again keeps the first original
    ducker.restore()
    assert volume.level == 0.8
    assert not state_path.exists()


def test_all_sessions_of_an_app_share_its_loudest_original(audio, make_ducker):
    loud, quiet = audio.add(FakeVolume(1.0)), audio.add(FakeVolume(0.4))
    other = audio.add(FakeVolume(1.0), process="chrome.exe")
    ducker = make_ducker()
    ducker.duck()
    assert (loud.level, quiet.level, other.level) == (0.25, 0.25, 1.0)
    ducker.restore()
    assert (loud.level, quiet.level) == (1.0, 1.0)


def test_ducked_restores_when_the_body_raises(audio, make_ducker):
    volume = audio.add(FakeVolume(0.6))
    with pytest.raises(RuntimeError, match="tts crashed"), make_ducker().ducked():
        raise RuntimeError("tts crashed")
    assert volume.level == 0.6


def test_failure_midway_through_duck_restores_and_does_not_raise(audio, make_ducker):
    volume = audio.add(FakeVolume(0.9, failing_calls={2}))
    ducker = make_ducker()
    ducker.duck()
    assert volume.level == 0.9
    assert not ducker.is_ducked


def test_restore_retries_when_sessions_cannot_be_listed(audio, make_ducker):
    volume = audio.add(FakeVolume(0.7))
    ducker = make_ducker()
    ducker.duck()
    audio.lookup_error = OSError("audio service restarting")
    ducker.restore()
    assert ducker.is_ducked
    audio.lookup_error = None
    ducker.restore()
    assert volume.level == 0.7


def test_app_exiting_mid_restore_is_recovered_after_it_restarts(audio, make_ducker):
    # Fade back (call 6) and the direct set (call 7) both fail as the app exits.
    audio.add(FakeVolume(0.8, failing_calls={6, 7}))
    ducker = make_ducker()
    ducker.duck()
    ducker.restore()
    volume = audio.restart_app(0.2)  # Windows restores the ducked per-app level
    ducker.duck()
    assert volume.level == pytest.approx(0.2)  # 0.25 x the true 0.8, not 0.05
    ducker.restore()
    assert volume.level == 0.8


def test_app_gone_at_restore_is_recovered_when_it_comes_back(audio, make_ducker):
    audio.add(FakeVolume(0.8))
    ducker = make_ducker()
    ducker.duck()
    audio.sessions.clear()
    ducker.restore()
    volume = audio.restart_app(0.2)
    ducker.duck()
    assert volume.level == pytest.approx(0.2)  # ducked once, from 0.8
    ducker.restore()
    assert volume.level == 0.8


def test_app_already_back_at_restore_gets_its_original(audio, make_ducker):
    audio.add(FakeVolume(0.8))
    ducker = make_ducker()
    ducker.duck()
    volume = audio.restart_app(0.2)  # new session, same app id
    ducker.restore()
    assert volume.level == 0.8


def test_new_ducker_undoes_a_crashed_run(audio, make_ducker, state_path):
    volume = audio.add(FakeVolume(0.8))
    make_ducker().duck()  # the process then dies without restoring
    make_ducker()
    assert volume.level == 0.8
    assert not state_path.exists()


def test_crash_recovery_leaves_a_volume_the_user_changed(audio, make_ducker, state_path):
    volume = audio.add(FakeVolume(0.8))
    make_ducker().duck()
    volume.level = 0.5  # the user turned Spotify up while audiohub was down
    make_ducker()
    assert volume.level == 0.5
    assert not state_path.exists()


def test_restore_waits_for_a_duck_that_is_still_fading(audio, make_ducker):
    # A task cancelled during an executor duck() calls restore() at once;
    # restore must not run first and leave the rest of the fade to win.
    volume = audio.add(BlockingVolume(0.8))
    ducker = make_ducker()
    duck_thread = threading.Thread(target=ducker.duck)
    duck_thread.start()
    assert volume.first_set.wait(timeout=2)
    restore_thread = threading.Thread(target=ducker.restore)
    restore_thread.start()
    volume.release.set()
    duck_thread.join(timeout=2)
    restore_thread.join(timeout=2)
    assert volume.level == 0.8
    assert not ducker.is_ducked


def test_com_initialisation_failure_never_raises(audio, make_ducker, monkeypatch):
    @contextlib.contextmanager
    def broken_com():
        raise OSError("CoInitialize failed")
        yield

    audio.add(FakeVolume(0.8))
    monkeypatch.setattr(ducking_module, "com_initialized", broken_com)
    ducker = make_ducker()
    ducker.duck()
    ducker.restore()
    assert not ducker.is_ducked


def test_crash_state_file_holds_original_and_ducked_level(audio, make_ducker, state_path):
    audio.add(FakeVolume(0.8))
    make_ducker().duck()
    saved = json.loads(state_path.read_text())
    assert saved == {SPOTIFY: {"original": 0.8, "ducked": pytest.approx(0.2)}}


class BlockingVolume(FakeVolume):
    """A volume whose first set call blocks until the test releases it."""

    def __init__(self, level: float) -> None:
        super().__init__(level)
        self.first_set = threading.Event()
        self.release = threading.Event()

    def SetMasterVolume(self, level: float, event_context: object) -> None:  # noqa: N802
        if not self.first_set.is_set():
            self.first_set.set()
            self.release.wait(timeout=2)
        super().SetMasterVolume(level, event_context)
