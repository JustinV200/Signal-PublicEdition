"""`audiohub run --phone`: the hub with the phone page as its mic and speaker.

Builds the same hub as `run` (brain, kernel, KernelServer, PC music ducking)
but hears through RemoteFrameSource, speaks through RemoteSpeaker, mirrors
the status line to the page, and uses `[phone] echo_tail_s` (see
`phone_audio_settings`). The phone page server starts first, so the phone can
connect while the models load.
"""

import dataclasses

from audiohub.config import AudioSettings, Settings
from audiohub.loop import Conversation, HubIo, HubStartError, StatusLine, build_parts
from audiohub.phone import (
    PhoneLink,
    PhoneServer,
    RemoteFrameSource,
    RemoteSpeaker,
    phone_link_lines,
)


async def run_phone_hub(settings: Settings) -> None:
    """Serve the phone page and run the hub through it until cancelled.

    Raises:
        HubStartError: If the phone page port or the notification port is taken.
    """
    link = PhoneLink()
    io = HubIo(
        source=RemoteFrameSource(link),
        speaker=RemoteSpeaker(link),
        status=StatusLine(on_show=link.show_status),
    )
    hub_settings = dataclasses.replace(settings, audio=phone_audio_settings(settings))
    parts = build_parts(hub_settings, listen=True, io=io)
    server = PhoneServer(link, settings.phone)
    try:
        await server.start()
    except OSError as error:
        raise HubStartError(
            f"can't serve the phone page on port {settings.phone.port} ({error}); "
            "is another `audiohub run --phone` running?"
        ) from error
    try:
        print_phone_links(settings, server.token)
        await Conversation(hub_settings, True, parts).run()
    finally:
        await server.close()


def phone_audio_settings(settings: Settings) -> AudioSettings:
    """The `[audio]` settings for phone mode, with the phone's longer lag.

    The phone adds network lag to its Bluetooth lag, so `[phone] echo_tail_s`
    replaces `echo_tail_s`, and the user hears Claude stop later by the same
    amount, so `reply_after_s` moves by it too (capped at the new tail).

    Args:
        settings: The loaded settings.

    Returns:
        A copy of `settings.audio` with both values changed.
    """
    audio, phone_tail_s = settings.audio, settings.phone.echo_tail_s
    extra_lag_s = phone_tail_s - audio.echo_tail_s
    reply_after_s = min(max(0.0, audio.reply_after_s + extra_lag_s), phone_tail_s)
    return dataclasses.replace(audio, echo_tail_s=phone_tail_s, reply_after_s=reply_after_s)


def print_phone_links(settings: Settings, token: str) -> None:
    """Print where to open the phone page, with the token link."""
    for line in phone_link_lines(settings.phone, token):
        print(f"phone: {line}", flush=True)
