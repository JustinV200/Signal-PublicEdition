"""`audiohub music ACTION`: control music (Spotify, or the Windows media session) from a terminal.

Actions: status, login, play, pause, toggle, next, prev, volume N,
play-search QUERY [--kind K], queue QUERY. `[music] backend` picks the
backend. A command the backend can't carry out prints its speakable reason
to stderr and exits 1.
"""

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import audiohub.music as music_api
from audiohub.cli.command import Command
from audiohub.cli.options import add_global_options
from audiohub.config import MusicSettings, Settings
from audiohub.music import (
    SEARCH_KINDS,
    MusicController,
    MusicUnavailable,
    NowPlaying,
    UnavailableReason,
    UnsupportedOperation,
    check_volume_percent,
)

# The Spotify-side names (create_controller, SpotifyController, SMTC_BACKEND)
# are read off `music_api` when used, so they load lazily (see audiohub.music).

EXIT_OK = 0
EXIT_MUSIC_UNAVAILABLE = 1
EXIT_BAD_ARGUMENT = 2


@dataclass(frozen=True)
class _SimpleAction:
    help: str
    send: Callable[[MusicController], Awaitable[None]]
    done_message: str


# Actions that call one argument-less controller method and print a confirmation.
_SIMPLE_ACTIONS: dict[str, _SimpleAction] = {
    "play": _SimpleAction("resume playback", lambda music: music.play(), "Playing."),
    "pause": _SimpleAction("pause playback", lambda music: music.pause(), "Paused."),
    "toggle": _SimpleAction("play or pause", lambda music: music.toggle(), "Toggled."),
    "next": _SimpleAction("skip to the next track", lambda music: music.next(), "Skipped."),
    "prev": _SimpleAction("go back a track", lambda music: music.previous(), "Went back."),
}


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the music actions as sub-commands, each accepting the global options too."""
    actions = parser.add_subparsers(dest="music_action", required=True, metavar="ACTION")
    _add_action(actions, "status", "show the music backend, Spotify login state and what's playing")
    _add_action(actions, "login", "log in to Spotify in the browser (one-time; needs Premium)")
    for name, action in _SIMPLE_ACTIONS.items():
        _add_action(actions, name, action.help)
    volume = _add_action(actions, "volume", "set Spotify's volume (0-100)")
    volume.add_argument("percent", type=parse_volume_percent, metavar="N")
    play_search = _add_action(actions, "play-search", "search Spotify and play the best match")
    play_search.add_argument("query", nargs="+", help="what to search for (quotes optional)")
    play_search.add_argument("--kind", choices=SEARCH_KINDS, default="track")
    queue = _add_action(actions, "queue", "search Spotify for a track and queue it")
    queue.add_argument("query", nargs="+", help="what to search for (quotes optional)")


def parse_volume_percent(text: str) -> int:
    """Parse a volume argument: a whole number from 0 to 100.

    Raises:
        argparse.ArgumentTypeError: If it isn't one.
    """
    try:
        return check_volume_percent(int(text))
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"expected a whole number 0-100, got {text!r}") from error


def run(args: argparse.Namespace, settings: Settings) -> int:
    """Run one music action.

    Returns:
        0 on success, 1 if the backend couldn't do it, 2 for a bad argument.
    """
    try:
        if args.music_action == "login":
            return _login(settings.music)
        if args.music_action == "status":
            return asyncio.run(_print_status(settings.music))
        print(asyncio.run(_run_action(args, music_api.create_controller(settings.music))))
    except (MusicUnavailable, UnsupportedOperation) as error:
        print(f"audiohub: music: {error}", file=sys.stderr)
        return EXIT_MUSIC_UNAVAILABLE
    except ValueError as error:
        print(f"audiohub: music: {error}", file=sys.stderr)
        return EXIT_BAD_ARGUMENT
    return EXIT_OK


def describe_now_playing(current: NowPlaying | None) -> str:
    """Format the current track for the status output.

    Returns:
        e.g. "Babydoll by Dominic Fike [paused] from smtc:MSEdge", or "nothing".
    """
    if current is None:
        return "nothing"
    state = "playing" if current.is_playing else "paused"
    return f"{current.describe()} [{state}] from {current.source}"


async def _run_action(args: argparse.Namespace, music: MusicController) -> str:
    simple = _SIMPLE_ACTIONS.get(args.music_action)
    if simple is not None:
        await simple.send(music)
        return simple.done_message
    if args.music_action == "volume":
        await music.set_volume(args.percent)
        return f"Volume set to {args.percent}%."
    query = " ".join(args.query)
    if args.music_action == "play-search":
        return f"Playing {await music.search_and_play(query, args.kind)}."
    return f"Queued {await music.queue(query)}."


async def _print_status(music_settings: MusicSettings) -> int:
    print(f"Backend:     {music_settings.backend}")
    if music_settings.backend != music_api.SMTC_BACKEND:
        print(f"Spotify:     {_spotify_login_state(music_settings)}")
    try:
        current = await music_api.create_controller(music_settings).now_playing()
    except MusicUnavailable as error:
        print(f"Now playing: unknown ({error})")
        return EXIT_OK
    print(f"Now playing: {describe_now_playing(current)}")
    return EXIT_OK


def _spotify_login_state(music_settings: MusicSettings) -> str:
    try:
        music_api.SpotifyController(music_settings).check_ready()
    except MusicUnavailable as error:
        return f"{error.reason.value.replace('_', ' ')}: {error}"
    return "logged in"


def _login(music_settings: MusicSettings) -> int:
    spotify = music_api.SpotifyController(music_settings)
    try:
        spotify.check_ready()
    except MusicUnavailable as error:
        # Fail before promising a browser if there's no client ID to log in with.
        if error.reason is UnavailableReason.NOT_CONFIGURED:
            raise
    print("Opening your browser to log in to Spotify. Approve access, then come back here.")
    print(f"Logged in to Spotify. Token cached at {spotify.login()}")
    return EXIT_OK


def _add_action(
    actions: "argparse._SubParsersAction[argparse.ArgumentParser]", name: str, help_text: str
) -> argparse.ArgumentParser:
    action = actions.add_parser(name, help=help_text, description=help_text)
    add_global_options(action, is_subcommand=True)
    return action


COMMAND = Command(
    name="music",
    help="control music: Spotify, or the Windows media session as a fallback",
    add_arguments=add_arguments,
    run=run,
)
