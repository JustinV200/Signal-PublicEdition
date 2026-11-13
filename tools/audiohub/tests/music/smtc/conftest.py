"""Fixtures for Windows media session tests: fake winrt sessions and a session manager.

Real winrt try_*_async methods return awaitable IAsyncOperation objects; the
fakes use coroutines, which await the same way.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from audiohub.music import SmtcController
from audiohub.music.smtc.controller import PAUSED_STATUS, PLAYING_STATUS
from audiohub.music.smtc.sessions import COLLECTIONS_MODULE


@dataclass
class FakeProperties:
    title: str = "Babydoll"
    artist: str = "Dominic Fike"
    album_title: str = "Sunburn"


@dataclass
class FakePlaybackInfo:
    playback_status: int


class FakeSession:
    """A media session that records commands and answers `accepts` to each.

    Set `failure` to an OSError to make every awaited call raise it, the way
    winrt reports a failed HRESULT.
    """

    def __init__(self, app_id: str, *, status: int = PLAYING_STATUS) -> None:
        self.source_app_user_model_id = app_id
        self.status = status
        self.properties: FakeProperties | None = FakeProperties()
        self.accepts = True
        self.failure: OSError | None = None
        # True: pause is accepted but the status stays PLAYING (an app that ignores it).
        self.ignores_pause = False
        self.commands: list[str] = []

    def get_playback_info(self) -> FakePlaybackInfo:
        return FakePlaybackInfo(self.status)

    async def try_get_media_properties_async(self) -> FakeProperties | None:
        if self.failure is not None:
            raise self.failure
        return self.properties

    async def _command(self, name: str) -> bool:
        self.commands.append(name)
        if self.failure is not None:
            raise self.failure
        return self.accepts

    def try_play_async(self):
        return self._command("play")

    def try_pause_async(self):
        if not self.ignores_pause:
            self.status = PAUSED_STATUS
        return self._command("pause")

    def try_toggle_play_pause_async(self):
        return self._command("toggle")

    def try_skip_next_async(self):
        return self._command("next")

    def try_skip_previous_async(self):
        return self._command("previous")


class FakeManager:
    """A session manager. With `can_list=False` it acts like winrt without the
    collections projection installed."""

    def __init__(
        self, sessions: list[FakeSession], current: FakeSession | None, *, can_list: bool = True
    ) -> None:
        self.sessions = sessions
        self.current = current
        self.can_list = can_list

    def get_current_session(self) -> FakeSession | None:
        return self.current

    def get_sessions(self) -> list[FakeSession]:
        if not self.can_list:
            raise ModuleNotFoundError(
                f"No module named {COLLECTIONS_MODULE!r}", name=COLLECTIONS_MODULE
            )
        return list(self.sessions)


@pytest.fixture(autouse=True)
def no_pause_check_delay(monkeypatch) -> None:
    """Skip the real wait between pause-confirmation reads."""
    monkeypatch.setattr("audiohub.music.smtc.controller.PAUSE_CHECK_DELAY_S", 0)


@pytest.fixture
def make_session() -> type[FakeSession]:
    return FakeSession


@pytest.fixture
def make_manager() -> type[FakeManager]:
    return FakeManager


@pytest.fixture
def controller_for() -> Callable[[FakeManager], SmtcController]:
    """Return a function building an SmtcController over a FakeManager."""

    def build(manager: FakeManager) -> SmtcController:
        async def request_manager() -> FakeManager:
            return manager

        return SmtcController(request_manager)

    return build


@pytest.fixture
def edge_and_spotify() -> tuple[FakeSession, FakeSession]:
    """Edge (the current session) plus a paused Spotify session."""
    return FakeSession("MSEdge"), FakeSession("Spotify.exe", status=PAUSED_STATUS)
