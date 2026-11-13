"""End-to-end test of the phone bridge: a WebSocket client streams speech, TTS PCM comes back.

It lives with the Conversation tests to reuse the loop fakes (brain, TTS,
ducker, dispatcher). The phone side is real: PhoneServer, RemoteFrameSource
and RemoteSpeaker, with the real Silero VAD and segmenter. Only Whisper is
scripted. The speech is tests/fixtures/hey_claude.wav, a synthesized "Hey Claude,
what's the weather like in London today?"
"""

import asyncio
import io
import struct
from pathlib import Path

import aiohttp
import numpy as np
import pytest

from audiohub.config import AudioSettings, PhoneSettings, Settings
from audiohub.kernel import Kernel, KernelServer
from audiohub.loop import (
    Conversation,
    ConversationParts,
    Hearing,
    StatusLine,
    VoiceOutput,
)
from audiohub.loop.hearing import read_wav_mono
from audiohub.phone import (
    COOKIE_NAME,
    PhoneLink,
    PhoneServer,
    RemoteFrameSource,
    RemoteSpeaker,
    session_cookie_value,
)
from audiohub.stt import SAMPLE_RATE, UtteranceSegmenter, VoiceActivityDetector

# tests/fixtures, from tests/loop/conversation.
SPEECH_WAV = Path(__file__).parents[2] / "fixtures" / "hey_claude.wav"
TRANSCRIPT = "Hey Claude, what's the time?"
PHONE_CHUNK_SAMPLES = 1000  # not a multiple of 512, on purpose
TRAILING_SILENCE_S = 1.5
FAKE_TTS_RATE = 24000  # what the loop conftest's FakeSynthesizer returns
# The chime has its own tests; here the first sound back is the reply.
SETTINGS = Settings(audio=AudioSettings(echo_tail_s=0.05, wake_chime=False))


class ScriptedTranscriber:
    """Stands in for Whisper: returns TRANSCRIPT and records each utterance's length."""

    device_in_use, model_in_use = "cpu", "scripted"

    def __init__(self) -> None:
        self.lengths: list[int] = []

    def load(self) -> None:
        pass

    def transcribe(self, audio: np.ndarray) -> str:
        self.lengths.append(len(audio))
        return TRANSCRIPT


def _build_parts(tmp_path, link, fakes, transcriber) -> tuple[ConversationParts, io.StringIO]:
    status_stream = io.StringIO()
    status = StatusLine(status_stream, on_show=link.show_status)
    kernel = Kernel(SETTINGS.kernel, dispatcher=fakes.Dispatcher())
    voice = VoiceOutput(fakes.Synthesizer(), RemoteSpeaker(link), fakes.Ducker())
    segmenter = UtteranceSegmenter(VoiceActivityDetector(SETTINGS.vad.threshold), SETTINGS.vad)
    hearing = Hearing(RemoteFrameSource(link), segmenter, transcriber)
    server = KernelServer(kernel, "127.0.0.1", 0, token_path=tmp_path / "ipc-token")
    parts = ConversationParts(kernel, server, voice, status, hearing, fakes.Brain())
    return parts, status_stream


def _speech_pcm_chunks() -> list[bytes]:
    speech = read_wav_mono(SPEECH_WAV)
    audio = np.concatenate([speech, np.zeros(int(TRAILING_SILENCE_S * SAMPLE_RATE))])
    pcm = np.round(np.clip(audio, -1, 1) * 32767).astype("<i2")
    return [
        pcm[start : start + PHONE_CHUNK_SAMPLES].tobytes()
        for start in range(0, len(pcm), PHONE_CHUNK_SAMPLES)
    ]


async def _receive_until_speech(socket) -> tuple[list[dict], bytes]:
    """Collect control messages until the first speech chunk arrives."""
    controls = []
    while True:
        message = await socket.receive(timeout=10)
        if message.type == aiohttp.WSMsgType.BINARY:
            return controls, message.data
        controls.append(message.json())


@pytest.mark.asyncio
async def test_phone_speech_reaches_the_brain_and_tts_pcm_comes_back(tmp_path, fakes):
    link, transcriber = PhoneLink(), ScriptedTranscriber()
    parts, status_stream = _build_parts(tmp_path, link, fakes, transcriber)
    phone = PhoneServer(link, PhoneSettings(port=0), token_path=tmp_path / "phone-token")
    async with phone, aiohttp.ClientSession() as http:
        hub = asyncio.create_task(Conversation(SETTINGS, True, parts).run())
        base = f"http://127.0.0.1:{phone.port}"
        headers = {"Origin": base, "Cookie": f"{COOKIE_NAME}={session_cookie_value(phone.token)}"}
        try:
            async with http.ws_connect(f"{base}/ws", headers=headers) as socket:
                await fakes.wait_until(
                    lambda: link.is_connected and "] ready" in status_stream.getvalue()
                )
                for chunk in _speech_pcm_chunks():
                    await socket.send_bytes(chunk)
                controls, speech = await _receive_until_speech(socket)
                chunk_id, rate = struct.unpack_from("<II", speech)
                await socket.send_json({"type": "played", "id": chunk_id})
                await fakes.wait_until(lambda: not parts.voice.speaking)
        finally:
            hub.cancel()
            await asyncio.gather(hub, return_exceptions=True)
    assert parts.brain.requests == ["what's the time?"]
    # The VAD cut one utterance out of the stream, about as long as the speech.
    assert len(transcriber.lengths) == 1
    assert transcriber.lengths[0] / SAMPLE_RATE > 0.5
    assert rate == FAKE_TTS_RATE
    assert np.frombuffer(speech[8:], dtype="<i2").max() == round(0.1 * 32767)
    # Barge-in (the default) keeps the phone's mic on while Claude speaks.
    assert {"type": "mic", "on": False} not in controls
    assert any(c.get("label") == "thinking" for c in controls if c["type"] == "status")
