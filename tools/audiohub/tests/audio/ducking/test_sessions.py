"""Tests for audiohub.audio.ducking.sessions: turning pycaw session controls into AppSessions.

The COM session enumeration and psutil are mocked; the filtering logic is real.
"""

import contextlib

import psutil
import pytest

from audiohub.audio.ducking import sessions


class FakeControl:
    """Stands in for IAudioSessionControl2."""

    def __init__(self, process_id: int) -> None:
        self._process_id = process_id
        self.volume = object()

    def GetProcessId(self) -> int:  # noqa: N802 - mirrors the COM method
        return self._process_id

    def GetSessionIdentifier(self) -> str:  # noqa: N802
        return f"app-of-{self._process_id}"

    def QueryInterface(self, interface: object) -> object:  # noqa: N802
        return self.volume


class FakeProcess:
    NAMES = {10: "Spotify.exe", 20: "chrome.exe"}

    def __init__(self, process_id: int) -> None:
        if process_id not in self.NAMES:
            raise psutil.NoSuchProcess(process_id)
        self._process_id = process_id

    def name(self) -> str:
        return self.NAMES[self._process_id]


@pytest.fixture
def controls(monkeypatch: pytest.MonkeyPatch) -> list[FakeControl]:
    fake_controls = [
        FakeControl(0),  # System Sounds
        FakeControl(10),  # Spotify, two sessions
        FakeControl(10),
        FakeControl(20),  # chrome
        FakeControl(30),  # a process that has exited
    ]
    monkeypatch.setattr(sessions, "_session_controls", lambda: iter(fake_controls))
    monkeypatch.setattr(sessions.psutil, "Process", FakeProcess)
    return fake_controls


def test_find_sessions_matches_process_names_case_insensitively(controls):
    found = sessions.find_sessions(["SPOTIFY.EXE"])
    assert [session.volume for session in found] == [controls[1].volume, controls[2].volume]
    assert found[0].volume is controls[1].volume
    assert found[0].process_id == 10
    assert found[0].app_id == "app-of-10"


def test_find_sessions_with_no_match_is_empty(controls):
    assert sessions.find_sessions(["vlc.exe"]) == []


def test_system_sounds_and_exited_processes_are_skipped(controls, monkeypatch):
    monkeypatch.setattr(sessions, "com_initialized", contextlib.nullcontext)
    assert sessions.list_session_process_names() == ["Spotify.exe", "chrome.exe"]


def test_com_initialized_balances_init_and_uninit(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(sessions.comtypes, "CoInitialize", lambda: calls.append("init"))
    monkeypatch.setattr(sessions.comtypes, "CoUninitialize", lambda: calls.append("uninit"))
    with sessions.com_initialized():
        calls.append("body")
    assert calls == ["init", "body", "uninit"]


def test_com_initialized_skips_uninit_when_thread_is_in_another_mode(monkeypatch):
    def changed_mode() -> None:
        # OSError's 4th argument is the Windows error code (HRESULT here).
        raise OSError(0, "changed mode", None, sessions.RPC_E_CHANGED_MODE)

    uninit_calls: list[str] = []
    monkeypatch.setattr(sessions.comtypes, "CoInitialize", changed_mode)
    monkeypatch.setattr(sessions.comtypes, "CoUninitialize", lambda: uninit_calls.append("x"))
    with sessions.com_initialized():
        pass
    assert uninit_calls == []
