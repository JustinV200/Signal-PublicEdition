"""Tests for audiohub.music.smtc.controller: SmtcController over fake winrt sessions."""

import pytest

from audiohub.music import MusicUnavailable, NowPlaying, UnavailableReason, UnsupportedOperation
from audiohub.music.smtc.controller import PAUSED_STATUS, PLAYING_STATUS, STOPPED_STATUS

# GlobalSystemMediaTransportControlsSessionPlaybackStatus.CHANGING: mid track change.
CHANGING_STATUS = 2

COMMANDS = [
    ("play", "play"),
    ("pause", "pause"),
    ("toggle", "toggle"),
    ("next", "next"),
    ("previous", "previous"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "command"), COMMANDS)
async def test_commands_go_to_the_spotify_session(
    controller_for, make_manager, edge_and_spotify, method, command
):
    edge, spotify = edge_and_spotify
    spotify.status = PLAYING_STATUS  # so pause has something to pause
    controller = controller_for(make_manager([edge, spotify], current=edge))
    await getattr(controller, method)()
    assert spotify.commands == [command]
    assert edge.commands == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "commands"),
    [(PAUSED_STATUS, []), (STOPPED_STATUS, []), (CHANGING_STATUS, ["pause"])],
    ids=["paused", "stopped", "changing track"],
)
async def test_pause_is_sent_unless_the_music_is_already_paused_or_stopped(
    controller_for, make_manager, edge_and_spotify, status, commands
):
    # Some apps refuse to pause twice; the hub may have paused the music already.
    edge, spotify = edge_and_spotify
    spotify.status = status
    await controller_for(make_manager([edge, spotify], current=edge)).pause()
    assert spotify.commands == commands
    assert edge.commands == []


@pytest.mark.asyncio
async def test_command_without_any_session_is_no_session(controller_for, make_manager):
    controller = controller_for(make_manager([], current=None))
    with pytest.raises(MusicUnavailable, match="open the Spotify app") as error:
        await controller.play()
    assert error.value.reason is UnavailableReason.NO_SESSION


@pytest.mark.asyncio
async def test_refused_command_names_the_app(controller_for, make_manager, make_session):
    edge = make_session("MSEdge")
    edge.accepts = False
    controller = controller_for(make_manager([edge], current=edge))
    with pytest.raises(MusicUnavailable, match="MSEdge didn't respond to skip") as error:
        await controller.next()
    assert error.value.reason is UnavailableReason.REQUEST_FAILED


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "action"), [("pause", "pause"), ("toggle", "play or pause")])
async def test_failed_hresult_on_a_command_is_request_failed(
    controller_for, make_manager, make_session, method, action
):
    spotify = make_session("Spotify.exe")
    spotify.failure = OSError("[WinError -2147023170] The remote procedure call failed")
    controller = controller_for(make_manager([spotify], current=spotify))
    with pytest.raises(MusicUnavailable, match=f"Spotify.exe didn't respond to {action}") as error:
        await getattr(controller, method)()
    assert error.value.reason is UnavailableReason.REQUEST_FAILED
    assert isinstance(error.value.__cause__, OSError)


@pytest.mark.asyncio
async def test_failed_hresult_reading_media_is_request_failed(
    controller_for, make_manager, make_session
):
    edge = make_session("MSEdge")
    edge.failure = OSError("RPC failed")
    with pytest.raises(MusicUnavailable, match="aren't responding") as error:
        await controller_for(make_manager([edge], current=edge)).now_playing()
    assert error.value.reason is UnavailableReason.REQUEST_FAILED


@pytest.mark.asyncio
async def test_failed_hresult_finding_sessions_is_request_failed(controller_for, make_manager):
    manager = make_manager([], current=None)

    def failing_get_sessions():
        raise OSError("RPC failed")

    manager.get_sessions = failing_get_sessions
    with pytest.raises(MusicUnavailable) as error:
        await controller_for(manager).play()
    assert error.value.reason is UnavailableReason.REQUEST_FAILED


@pytest.mark.asyncio
async def test_now_playing_reports_the_session_and_its_app(
    controller_for, make_manager, edge_and_spotify
):
    edge, spotify = edge_and_spotify
    controller = controller_for(make_manager([edge, spotify], current=edge))
    assert await controller.now_playing() == NowPlaying(
        title="Babydoll",
        artist="Dominic Fike",
        album="Sunburn",
        is_playing=False,
        source="smtc:Spotify.exe",
    )


@pytest.mark.asyncio
async def test_now_playing_without_session_or_media_is_none(
    controller_for, make_manager, make_session
):
    assert await controller_for(make_manager([], current=None)).now_playing() is None
    edge = make_session("MSEdge")
    edge.properties = None
    assert await controller_for(make_manager([edge], current=edge)).now_playing() is None


@pytest.mark.asyncio
async def test_volume_search_and_queue_are_unsupported(controller_for, make_manager):
    controller = controller_for(make_manager([], current=None))
    with pytest.raises(UnsupportedOperation, match="volume"):
        await controller.set_volume(50)
    with pytest.raises(UnsupportedOperation, match="search"):
        await controller.search_and_play("babydoll")
    with pytest.raises(UnsupportedOperation, match="queue"):
        await controller.queue("babydoll")


@pytest.mark.asyncio
async def test_pause_the_app_ignores_is_reported(controller_for, make_manager, make_session):
    spotify = make_session("Spotify.exe")
    spotify.ignores_pause = True
    controller = controller_for(make_manager([spotify], current=spotify))
    with pytest.raises(MusicUnavailable, match="still playing") as error:
        await controller.pause()
    assert error.value.reason is UnavailableReason.REQUEST_FAILED


@pytest.mark.asyncio
async def test_pause_then_now_playing_agree(controller_for, make_manager, make_session):
    spotify = make_session("Spotify.exe")
    controller = controller_for(make_manager([spotify], current=spotify))
    await controller.pause()
    assert (await controller.now_playing()).is_playing is False
