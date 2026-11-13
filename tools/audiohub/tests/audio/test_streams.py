"""Tests for audiohub.audio.streams: refresh, re-resolve, open, start and close.

sounddevice's device queries come from the fake_portaudio table; stream
classes and PortAudio's terminate/initialize are replaced with recorders.
"""

import pytest
import sounddevice as sd

from audiohub.audio import AudioStreamError, DeviceNotFoundError, streams


class RecordingStream:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.samplerate = kwargs["samplerate"]
        self.is_closed = False
        self.start_error: Exception | None = None

    def start(self) -> None:
        if self.start_error is not None:
            raise self.start_error

    def close(self) -> None:
        self.is_closed = True


@pytest.fixture
def portaudio(fake_portaudio, monkeypatch):
    """Fake device queries plus a log of PortAudio refreshes. Returns the log."""
    table = {"devices": fake_portaudio}
    refreshes: list[str] = []

    def query_devices(device=None, kind=None):
        if device is None and kind is None:
            return table["devices"]
        if device is None:
            # PortAudio's default device is the default host API's (MME, index 0).
            device = sd.query_hostapis(0)[f"default_{kind}_device"]
        return table["devices"][device]

    monkeypatch.setattr(sd, "query_devices", query_devices)
    monkeypatch.setattr(sd, "query_hostapis", _query_hostapis(sd.query_hostapis()))
    monkeypatch.setattr(sd, "_terminate", lambda: refreshes.append("terminate"))
    monkeypatch.setattr(sd, "_initialize", lambda: refreshes.append("initialize"))
    monkeypatch.setattr(sd, "InputStream", RecordingStream)
    monkeypatch.setattr(sd, "OutputStream", RecordingStream)
    yield refreshes, table
    streams._open_streams.clear()


def _query_hostapis(hostapis):
    return lambda index=None: hostapis if index is None else hostapis[index]


def test_spec_is_resolved_and_opened_mono_at_the_native_rate(portaudio):
    stream = streams.open_mono_stream("input", "BT-Glasses", callback=print)
    assert stream.kwargs["device"] == 5
    assert stream.kwargs["samplerate"] == 16000.0
    assert stream.kwargs["channels"] == 1
    assert stream.kwargs["dtype"] == "float32"


def test_wasapi_streams_auto_convert_rates(portaudio):
    stream = streams.open_mono_stream("output", "BT-Glasses", callback=print)
    assert isinstance(stream.kwargs["extra_settings"], sd.WasapiSettings)


def test_portaudio_is_refreshed_before_opening(portaudio):
    refreshes, _ = portaudio
    streams.open_mono_stream("input", None, callback=print)
    assert refreshes == ["terminate", "initialize"]


def test_no_refresh_while_another_stream_is_open(portaudio):
    refreshes, _ = portaudio
    first = streams.open_mono_stream("input", "BT-Glasses", callback=print)
    streams.open_mono_stream("output", "BT-Glasses", callback=print)
    assert len(refreshes) == 2
    streams.close_stream(first)
    assert first.is_closed


def test_refresh_resumes_once_every_stream_is_closed(portaudio):
    refreshes, _ = portaudio
    stream = streams.open_mono_stream("input", None, callback=print)
    streams.close_stream(stream)
    streams.open_mono_stream("input", None, callback=print)
    assert len(refreshes) == 4


def test_renumbered_devices_are_found_after_a_reconnect(portaudio, fake_portaudio):
    # A Bluetooth reconnect shifts every index by two; the spec still finds it.
    _, table = portaudio
    shifted = [{**device, "index": device["index"] + 2} for device in fake_portaudio]
    table["devices"] = [*fake_portaudio[:2], *shifted]
    stream = streams.open_mono_stream("input", "BT-Glasses", callback=print)
    assert stream.kwargs["device"] == 7


def test_unknown_spec_raises_device_not_found(portaudio):
    with pytest.raises(DeviceNotFoundError):
        streams.open_mono_stream("input", "nonexistent", callback=print)


def test_portaudio_refusal_names_the_device(portaudio, monkeypatch):
    def refuse(**kwargs):
        raise sd.PortAudioError("Invalid sample rate")

    monkeypatch.setattr(sd, "InputStream", refuse)
    with pytest.raises(AudioStreamError, match="input stream on device 5: Invalid sample rate"):
        streams.open_mono_stream("input", "BT-Glasses", callback=print)
    assert streams._open_streams == set()


def test_failed_start_closes_the_stream(portaudio):
    stream = streams.open_mono_stream("input", "BT-Glasses", callback=print)
    stream.start_error = sd.PortAudioError("Device unavailable")
    with pytest.raises(AudioStreamError, match="could not start.*Device unavailable"):
        streams.start_stream(stream)
    assert stream.is_closed
    assert streams._open_streams == set()


def test_open_recovers_after_a_failed_refresh(portaudio, monkeypatch):
    # Mimic sounddevice's init counter: terminating while it's 0 is an error.
    monkeypatch.setattr(sd, "_initialized", 1)
    failures = [sd.PortAudioError("Error initializing PortAudio")]

    def terminate() -> None:
        if sd._initialized == 0:
            raise sd.PortAudioError("PortAudio not initialized")
        sd._initialized -= 1

    def initialize() -> None:
        if failures:
            raise failures.pop()
        sd._initialized += 1

    monkeypatch.setattr(sd, "_terminate", terminate)
    monkeypatch.setattr(sd, "_initialize", initialize)
    with pytest.raises(AudioStreamError, match="refresh the sound device list"):
        streams.open_mono_stream("input", None, callback=print)
    streams.open_mono_stream("input", None, callback=print)
    assert sd._initialized == 1
