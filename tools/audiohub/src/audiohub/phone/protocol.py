"""The phone bridge's WebSocket wire format, in both directions.

Phone -> hub:
- binary: the phone mic as little-endian int16 mono PCM at 16 kHz, in chunks
  of any even length up to MAX_MIC_BYTES
- text: JSON control, only `{"type": "played", "id": N}`, sent when speech
  chunk N is (nearly) done playing

Hub -> phone:
- binary: one speech chunk, a SPEECH_HEADER (uint32 chunk id, uint32 sample
  rate, little-endian) followed by int16 mono PCM
- text: JSON control: `{"type": "mic", "on": bool}`, `{"type": "stop"}` and
  `{"type": "status", "label": str, "detail": str}`

page/app.js is the other end. Anything from the phone that breaks these
rules raises FrameError, and the server closes the socket.
"""

import json
import struct

import numpy as np

# One second of 16 kHz int16 audio. The page sends 64 ms chunks, so anything
# near this is a misbehaving client. Also aiohttp's cap on any inbound message.
MAX_MIC_BYTES = 32 * 1024
MAX_CONTROL_CHARS = 256
INT16_BYTES = 2
INT16_FULL_SCALE = 32768.0
INT16_MAX = 32767
SPEECH_HEADER = struct.Struct("<II")
PLAYED_TYPE = "played"


class FrameError(ValueError):
    """A WebSocket message from the phone breaks the protocol."""


def decode_mic_pcm(data: bytes) -> np.ndarray:
    """Turn one mic message into float32 samples in [-1, 1).

    Raises:
        FrameError: If the message is empty, too long, or not whole int16 samples.
    """
    if not data or len(data) > MAX_MIC_BYTES or len(data) % INT16_BYTES:
        raise FrameError(f"mic audio must be 1 to {MAX_MIC_BYTES} bytes of int16, got {len(data)}")
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / INT16_FULL_SCALE


def encode_speech(chunk_id: int, samples: np.ndarray, sample_rate: int) -> bytes:
    """Pack one speech chunk for the phone: header, then int16 PCM.

    Args:
        chunk_id: Echoed back in the phone's "played" message.
        samples: Mono float audio in [-1, 1]; louder values are clipped.
        sample_rate: The samples' rate in Hz.
    """
    pcm = np.round(np.clip(samples, -1.0, 1.0) * INT16_MAX).astype("<i2")
    return SPEECH_HEADER.pack(chunk_id, sample_rate) + pcm.tobytes()


def parse_played(text: str) -> int:
    """Parse the phone's only control message and return the played chunk id.

    Raises:
        FrameError: If it isn't exactly `{"type": "played", "id": <non-negative int>}`.
    """
    if len(text) > MAX_CONTROL_CHARS:
        raise FrameError(f"control message longer than {MAX_CONTROL_CHARS} characters")
    try:
        message = json.loads(text)
    except json.JSONDecodeError as error:
        raise FrameError(f"control message is not JSON: {error}") from error
    if not isinstance(message, dict) or set(message) != {"type", "id"}:
        raise FrameError("control message must be {type, id}")
    chunk_id = message["id"]
    # bool is an int subclass, so rule it out explicitly.
    is_valid_id = isinstance(chunk_id, int) and not isinstance(chunk_id, bool) and chunk_id >= 0
    if message["type"] != PLAYED_TYPE or not is_valid_id:
        raise FrameError("control message must be a played ack with a non-negative id")
    return chunk_id


def mic_message(is_on: bool) -> dict[str, object]:
    """Tell the page to send (True) or drop (False) mic audio."""
    return {"type": "mic", "on": is_on}


def stop_message() -> dict[str, object]:
    """Tell the page to cut all speech it is playing or has queued."""
    return {"type": "stop"}


def status_message(label: str, detail: str) -> dict[str, object]:
    """The hub's status line for the page, e.g. ("thinking", '"what time is it"')."""
    return {"type": "status", "label": label, "detail": detail}
