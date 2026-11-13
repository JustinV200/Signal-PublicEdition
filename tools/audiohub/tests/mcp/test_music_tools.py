"""Tests for the MCP music tools, driven against a fake `MusicController`."""

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from audiohub.mcp import format_now_playing
from audiohub.music import MusicUnavailable, NowPlaying, UnavailableReason, UnsupportedOperation

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (
            NowPlaying("Babydoll", "Dominic Fike", "Sunburn", True, "spotify"),
            "Playing: Babydoll by Dominic Fike, from the album Sunburn.",
        ),
        (
            NowPlaying("Babydoll", "Dominic Fike", "", False, "smtc:Spotify.exe"),
            "Paused: Babydoll by Dominic Fike.",
        ),
        (None, "Nothing is playing right now."),
    ],
)
async def test_format_now_playing(now, expected) -> None:
    assert format_now_playing(now) == expected


async def test_search_and_play_passes_checked_arguments_and_reports(music_tools, music) -> None:
    result = await music_tools.search_and_play("  Kind of Blue ", kind="album")
    assert result == "Now playing Kind of Blue by Some Artist."
    assert music.calls == [("search_and_play", ("Kind of Blue", "album"))]


async def test_play_liked_passes_shuffle_and_reports(music_tools, music) -> None:
    assert await music_tools.play_liked(shuffle=True) == "Now playing your Liked Songs."
    assert music.calls == [("play_liked", (True,))]


@pytest.mark.parametrize(
    ("method", "argument", "message"),
    [("set_volume", 101, "volume must be"), ("queue", "  ", "must not be empty")],
)
async def test_bad_arguments_are_tool_errors_before_any_call(
    music_tools, music, method, argument, message
) -> None:
    with pytest.raises(ToolError, match=message):
        await getattr(music_tools, method)(argument)
    assert music.calls == []


@pytest.mark.parametrize(
    "error",
    [
        MusicUnavailable(
            "Spotify isn't playing on any device; open the Spotify app",
            UnavailableReason.NO_ACTIVE_DEVICE,
        ),
        UnsupportedOperation("Volume needs Spotify; the media session can't set it."),
    ],
)
async def test_music_errors_become_their_speakable_message(music_tools, music, error) -> None:
    music.error = error
    assert await music_tools.set_volume(30) == str(error)


async def test_unexpected_errors_are_not_swallowed(music_tools, music) -> None:
    music.error = RuntimeError("bug")
    with pytest.raises(RuntimeError):
        await music_tools.pause()
