"""`PhoneLink`: the one phone WebSocket, shared by the server, the frame source and the speaker.

PhoneServer attaches each authenticated socket here. A newer socket replaces
the old one, which is closed with REPLACED_CLOSE_CODE so that page stops
reconnecting. RemoteFrameSource gets the mic through the audio sink, and
RemoteSpeaker sends speech and waits for the page's "played" acks. Control
messages (mic on/off, stop, status) are sent without waiting. The mic state
and the last status are replayed to each new socket, so a phone that
reconnects picks up where it left off. Use it from the event loop thread only.
"""

import asyncio
import itertools
import logging
from collections.abc import Callable
from typing import Any, Protocol

import numpy as np

from audiohub.audio import AudioStreamError

from .protocol import (
    decode_mic_pcm,
    encode_speech,
    mic_message,
    parse_played,
    status_message,
    stop_message,
)

logger = logging.getLogger(__name__)

# An application close code (4000-4999 are free for apps). page/app.js stops
# reconnecting when it sees it, so two open pages don't keep taking turns.
REPLACED_CLOSE_CODE = 4000
GOING_AWAY_CLOSE_CODE = 1001  # the hub is stopping; the page keeps retrying


class PhoneSocket(Protocol):
    """What PhoneLink needs from aiohttp's `WebSocketResponse`."""

    async def send_bytes(self, data: bytes) -> None:
        """Send one binary message."""
        ...

    async def send_json(self, data: Any) -> None:
        """Send one text message holding `data` as JSON."""
        ...

    async def close(self, *, code: int = ..., message: bytes = ...) -> bool:
        """Close the socket with a close code."""
        ...


class PhoneLink:
    """Carries mic audio, speech and control messages over the current phone socket."""

    def __init__(self) -> None:
        """Start with no phone connected, the mic on and no status yet."""
        self._socket: PhoneSocket | None = None
        self._audio_sink: Callable[[np.ndarray], None] | None = None
        self._played: dict[int, asyncio.Future[None]] = {}
        self._chunk_ids = itertools.count(1)
        self._is_mic_on = True
        self._last_status: dict[str, object] | None = None
        # Fire-and-forget sends, kept referenced so they aren't garbage collected.
        self._sends: set[asyncio.Task[None]] = set()

    @property
    def is_connected(self) -> bool:
        """Whether a phone socket is attached."""
        return self._socket is not None

    def set_audio_sink(self, sink: Callable[[np.ndarray], None]) -> None:
        """Hand every mic message, as float32 samples, to `sink` (RemoteFrameSource)."""
        self._audio_sink = sink

    async def attach(self, socket: PhoneSocket) -> None:
        """Make `socket` the phone, closing the one it replaces, and send it the current state.

        Raises:
            ConnectionError: If the new socket drops while the state is sent.
        """
        previous, self._socket = self._socket, socket
        if previous is not None:
            self._fail_pending("a newer phone connection replaced this one")
            await previous.close(code=REPLACED_CLOSE_CODE, message=b"replaced by a newer page")
        await socket.send_json(mic_message(self._is_mic_on))
        if self._last_status is not None:
            await socket.send_json(self._last_status)

    def detach(self, socket: PhoneSocket) -> None:
        """Forget `socket` if it is still the phone, failing speech that waits on it."""
        if socket is not self._socket:
            return
        self._socket = None
        self._fail_pending("the phone disconnected")

    async def disconnect(self) -> None:
        """Close the phone socket, if any, because the hub is stopping."""
        if self._socket is not None:
            await self._socket.close(code=GOING_AWAY_CLOSE_CODE, message=b"hub stopping")

    def receive_audio(self, data: bytes) -> None:
        """Pass one mic message to the audio sink.

        Raises:
            FrameError: If it isn't valid int16 PCM (see protocol.py).
        """
        samples = decode_mic_pcm(data)
        if self._audio_sink is not None:
            self._audio_sink(samples)

    def receive_control(self, text: str) -> None:
        """Handle a "played" ack from the phone.

        An ack for a chunk that was already stopped or timed out is ignored:
        it races with `stop()` on a slow network and means no harm.

        Raises:
            FrameError: If it isn't a valid ack (see protocol.py).
        """
        played = self._played.pop(parse_played(text), None)
        if played is not None and not played.done():
            played.set_result(None)

    async def send_speech(self, samples: np.ndarray, sample_rate: int) -> asyncio.Future[None]:
        """Send one speech chunk to the phone.

        Returns:
            A future that completes when the phone acks the chunk, or fails
            with AudioStreamError if the phone disconnects or is replaced first.

        Raises:
            AudioStreamError: If no phone is connected or the send fails.
        """
        socket = self._socket
        if socket is None:
            raise AudioStreamError("no phone is connected; open the phone page and tap Start")
        chunk_id = next(self._chunk_ids)
        played: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._played[chunk_id] = played
        # A stopped or timed-out chunk is cancelled by its waiter; drop it then.
        played.add_done_callback(lambda _: self._played.pop(chunk_id, None))
        try:
            await socket.send_bytes(encode_speech(chunk_id, samples, sample_rate))
        except ConnectionError as error:
            played.cancel()
            raise AudioStreamError(f"could not send speech to the phone: {error}") from error
        return played

    def set_mic(self, is_on: bool) -> None:
        """Tell the page to send (True) or drop (False) mic audio, now and after reconnects."""
        self._is_mic_on = is_on
        self._post(mic_message(is_on))

    def show_status(self, label: str, detail: str = "") -> None:
        """Show the hub's status on the page (a StatusLine `on_show` hook)."""
        self._last_status = status_message(label, detail)
        self._post(self._last_status)

    def stop_speech(self) -> None:
        """Tell the page to cut whatever speech it is playing or has queued."""
        self._post(stop_message())

    def _post(self, message: dict[str, object]) -> None:
        """Send a control message without waiting; dropped when no phone is connected."""
        if self._socket is None:
            return
        task = asyncio.create_task(_send_quietly(self._socket, message))
        self._sends.add(task)
        task.add_done_callback(self._sends.discard)

    def _fail_pending(self, reason: str) -> None:
        pending, self._played = self._played, {}
        for played in pending.values():
            if not played.done():
                played.set_exception(AudioStreamError(reason))


async def _send_quietly(socket: PhoneSocket, message: dict[str, object]) -> None:
    """Send a control message; a phone that already went away just misses it."""
    try:
        await socket.send_json(message)
    except ConnectionError as error:
        logger.debug("phone went away before a control message arrived: %s", error)
