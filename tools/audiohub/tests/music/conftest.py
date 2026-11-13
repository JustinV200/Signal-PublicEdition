"""Shared fixtures for music tests: a scripted MusicController fake.

`FakeController` records each call by method name. `failures` maps a method
name to the exception it should raise; `playing` is what now_playing returns.
"""

from collections.abc import Callable

import pytest

from audiohub.music import NowPlaying


class FakeController:
    """A MusicController that records calls and raises scripted errors."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[tuple] = []
        self.failures: dict[str, Exception] = {}
        self.playing: NowPlaying | None = None

    def _record(self, method: str, *args: object) -> None:
        self.calls.append((method, *args))
        if method in self.failures:
            raise self.failures[method]

    async def play(self) -> None:
        self._record("play")

    async def pause(self) -> None:
        self._record("pause")

    async def toggle(self) -> None:
        self._record("toggle")

    async def next(self) -> None:
        self._record("next")

    async def previous(self) -> None:
        self._record("previous")

    async def now_playing(self) -> NowPlaying | None:
        self._record("now_playing")
        return self.playing

    async def set_volume(self, percent: int) -> None:
        self._record("set_volume", percent)

    async def search_and_play(self, query: str, kind: str = "track") -> str:
        self._record("search_and_play", query, kind)
        return f"{self.name} played {query}"

    async def queue(self, query: str) -> str:
        self._record("queue", query)
        return f"{self.name} queued {query}"


@pytest.fixture
def make_controller() -> Callable[[str], FakeController]:
    """Return a factory for named FakeControllers."""
    return FakeController
