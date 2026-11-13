"""Public API of audiohub.phone: the phone bridge for `audiohub run --phone`.

The owner's glasses pair with the phone; a page on the phone streams its mic
to the hub and plays the hub's speech, over Tailscale HTTPS to a loopback
server here. `RemoteFrameSource` and `RemoteSpeaker` stand in for the local
mic and speaker in the voice loop, so everything else runs unchanged.

    link = PhoneLink()
    source, speaker = RemoteFrameSource(link), RemoteSpeaker(link)
    async with PhoneServer(link, settings.phone) as server:
        ...  # run the Conversation with source and speaker

Other packages import from here only.
"""

from .auth import COOKIE_NAME, session_cookie_value
from .frame_source import RemoteFrameSource
from .link import REPLACED_CLOSE_CODE, PhoneLink
from .page_links import phone_link_lines
from .protocol import FrameError
from .server import DEFAULT_TOKEN_PATH, PhoneServer
from .speaker import RemoteSpeaker

__all__ = [
    "COOKIE_NAME",
    "DEFAULT_TOKEN_PATH",
    "REPLACED_CLOSE_CODE",
    "FrameError",
    "PhoneLink",
    "PhoneServer",
    "RemoteFrameSource",
    "RemoteSpeaker",
    "phone_link_lines",
    "session_cookie_value",
]
