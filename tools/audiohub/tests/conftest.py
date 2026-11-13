"""Shared pytest fixtures for audiohub tests.

`fake_portaudio` replaces sounddevice's device queries with a small fixed
table modelled on the real machine: a USB headset, plus the user's Bluetooth
glasses as Windows really names them when connected (WASAPI and MME
`Headset (BT-Glasses-01)` input, `Headphones (BT-Glasses-01)` output; no Hands-Free
output endpoint) and as raw WDM-KS resource-string entries.
"""

from typing import Any

import pytest
import sounddevice as sd

MME, WASAPI, WDM_KS = 0, 1, 2

FAKE_HOSTAPIS: list[dict[str, Any]] = [
    {"name": "MME", "default_input_device": 1, "default_output_device": 2},
    {"name": "Windows WASAPI", "default_input_device": 3, "default_output_device": 4},
    {"name": "Windows WDM-KS", "default_input_device": -1, "default_output_device": -1},
]

RAW_BT_NAME = "Headset (@System32\\drivers\\bthhfenum.sys,#2;%1 Hands-Free%0\r\n;(BT Headphones))"
RAW_GLASSES_NAME = (
    "Headset (@System32\\drivers\\bthhfenum.sys,#2;%1 Hands-Free%0\r\n;(BT-Glasses-01))"
)

# (name, hostapi, max_input_channels, max_output_channels, default_samplerate)
_FAKE_DEVICE_ROWS = [
    ("Microsoft Sound Mapper - Input", MME, 2, 0, 44100.0),
    ("Microphone (USB Audio)", MME, 1, 0, 44100.0),
    ("Speakers (USB Audio)", MME, 0, 2, 44100.0),
    ("Microphone (USB Audio)", WASAPI, 2, 0, 48000.0),
    ("Speakers (USB Audio)", WASAPI, 0, 2, 48000.0),
    ("Headset (BT-Glasses-01)", WASAPI, 1, 0, 16000.0),
    ("Headphones (BT-Glasses-01)", WASAPI, 0, 2, 44100.0),
    ("Headset (BT-Glasses-01)", MME, 1, 0, 44100.0),
    ("Headphones (BT-Glasses-01)", MME, 0, 2, 44100.0),
    (RAW_GLASSES_NAME, WDM_KS, 1, 0, 16000.0),
    (RAW_BT_NAME, WDM_KS, 1, 0, 8000.0),
    ("Speakers", WASAPI, 0, 2, 48000.0),
]

FAKE_DEVICES: list[dict[str, Any]] = [
    {
        "index": index,
        "name": name,
        "hostapi": hostapi,
        "max_input_channels": inputs,
        "max_output_channels": outputs,
        "default_samplerate": rate,
    }
    for index, (name, hostapi, inputs, outputs, rate) in enumerate(_FAKE_DEVICE_ROWS)
]


@pytest.fixture
def fake_portaudio(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Make sounddevice report FAKE_DEVICES / FAKE_HOSTAPIS. Returns the device table."""
    monkeypatch.setattr(sd, "query_hostapis", lambda: FAKE_HOSTAPIS)
    monkeypatch.setattr(sd, "query_devices", lambda: FAKE_DEVICES)
    return FAKE_DEVICES
