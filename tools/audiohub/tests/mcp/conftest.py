"""Shared fakes for the MCP server tests: a recording kernel client and a scripted music player.

Nothing here opens a socket or talks to Spotify. `FakeKernelClient` stands in
for `kernel.send_notification`; `FakeMusicController` implements the
`MusicController` protocol and can be told to fail.
"""

from typing import Any

import pytest

from audiohub.config import IpcSettings
from audiohub.mcp import MusicTools, NotifyTool
from audiohub.music import NowPlaying, SearchKind

HUB = IpcSettings(host="127.0.0.1", port=8765)


class FakeKernelClient:
    """Records each notification and returns ids m1, m2, ... or raises `error` if set."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str, str, str]] = []
        self.error: Exception | None = None

    def __call__(self, host: str, port: int, source: str, text: str, priority: str) -> str:
        self.calls.append((host, port, source, text, priority))
        if self.error is not None:
            raise self.error
        return f"m{len(self.calls)}"


class FakeMusicController:
    """A `MusicController` that records calls by name and returns scripted results.

    Set `error` to make every call raise it. now_playing reports nothing loaded.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.error: Exception | None = None

    def _record(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))
        if self.error is not None:
            raise self.error

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
        return None

    async def set_volume(self, percent: int) -> None:
        self._record("set_volume", percent)

    async def search_and_play(self, query: str, kind: SearchKind = "track") -> str:
        self._record("search_and_play", query, kind)
        return f"{query} by Some Artist"

    async def play_liked(self, shuffle: bool | None = None) -> str:
        self._record("play_liked", shuffle)
        return "your Liked Songs"

    async def queue(self, query: str) -> str:
        self._record("queue", query)
        return f"{query} by Some Artist"


@pytest.fixture
def kernel_client() -> FakeKernelClient:
    return FakeKernelClient()


@pytest.fixture
def music() -> FakeMusicController:
    return FakeMusicController()


@pytest.fixture
def notify_tool(kernel_client: FakeKernelClient) -> NotifyTool:
    return NotifyTool(HUB, send=kernel_client)


@pytest.fixture
def music_tools(music: FakeMusicController) -> MusicTools:
    return MusicTools(music)
