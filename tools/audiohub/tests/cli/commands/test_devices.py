"""Tests for the `audiohub devices` command, with sounddevice mocked by fake_portaudio."""

import pytest
import sounddevice as sd

from audiohub.audio import list_devices
from audiohub.cli import main
from audiohub.cli.commands.devices import format_device_line
from audiohub.config import loader


def _raw_device(index: int, name: str, hostapi: int, inputs: int = 0, outputs: int = 0) -> dict:
    return {
        "index": index,
        "name": name,
        "hostapi": hostapi,
        "max_input_channels": inputs,
        "max_output_channels": outputs,
        "default_samplerate": 16000.0,
    }


@pytest.fixture(autouse=True)
def no_local_config(tmp_path, monkeypatch):
    # Keep a real tools/audiohub/audiohub.toml from changing these tests.
    monkeypatch.setattr(loader, "DEFAULT_CONFIG_PATH", tmp_path / "absent.toml")


def test_lists_preferred_hostapis_with_markers(fake_portaudio, capsys):
    assert main(["devices"]) == 0
    output = capsys.readouterr().out
    assert output.index("Windows WASAPI") < output.index("MME")
    assert "Windows WDM-KS" not in output
    assert "Microphone (USB Audio)  [default input]" in output
    assert "Headset (BT-Glasses-01)  [hands-free]" in output
    assert "Headphones (BT-Glasses-01)  [bluetooth]" in output
    assert "input:  system default" in output


def test_all_flag_adds_other_hostapis_with_clean_names(fake_portaudio, capsys):
    assert main(["devices", "--all"]) == 0
    output = capsys.readouterr().out
    assert "Windows WDM-KS" in output
    assert "Headset (BT-Glasses-01 Hands-Free)  [hands-free]" in output
    assert "Headset (BT Headphones Hands-Free)  [hands-free]" in output


def test_configured_devices_are_resolved(fake_portaudio, capsys):
    assert main(["devices", "--input-device", "bt-glasses", "--output-device", "BT-Glasses"]) == 0
    output = capsys.readouterr().out
    assert "'bt-glasses' -> 5 Headset (BT-Glasses-01) (Windows WASAPI)" in output
    assert "'BT-Glasses' -> 6 Headphones (BT-Glasses-01) (Windows WASAPI)" in output


def test_configured_index_is_resolved(fake_portaudio, capsys):
    assert main(["devices", "--output-device", "8"]) == 0
    assert "8 -> 8 Headphones (BT-Glasses-01) (MME)" in capsys.readouterr().out


def test_unresolvable_device_is_shown_and_fails(fake_portaudio, capsys):
    assert main(["devices", "--input-device", "nonexistent"]) == 1
    assert "'nonexistent' -> NOT FOUND" in capsys.readouterr().out


def test_hint_shown_when_bluetooth_is_only_under_hidden_hostapis(monkeypatch, capsys):
    # The real machine today: the glasses are paired but only WDM-KS lists them.
    hostapis = [
        {"name": "Windows WASAPI", "default_input_device": 0, "default_output_device": -1},
        {"name": "Windows WDM-KS", "default_input_device": -1, "default_output_device": -1},
    ]
    devices = [
        _raw_device(0, "Microphone (USB Audio)", hostapi=0, inputs=1),
        _raw_device(1, "Headset (BT-Glasses-01 Hands-Free)", hostapi=1, inputs=1),
    ]
    monkeypatch.setattr(sd, "query_hostapis", lambda: hostapis)
    monkeypatch.setattr(sd, "query_devices", lambda: devices)
    assert main(["devices"]) == 0
    assert "probably paired but not connected" in capsys.readouterr().out


def test_no_hint_when_bluetooth_is_visible(fake_portaudio, capsys):
    main(["devices"])
    assert "probably paired" not in capsys.readouterr().out


def test_device_line_format(fake_portaudio):
    line = format_device_line(list_devices()[3], None)
    assert line == "    3  in       2ch  48000 Hz  Microphone (USB Audio)  [default input]"
