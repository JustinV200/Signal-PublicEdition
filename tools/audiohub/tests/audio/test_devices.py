"""Tests for audiohub.audio.devices: listing and resolving devices (sounddevice mocked)."""

import pytest

from audiohub.audio import DeviceNotFoundError, list_devices, resolve_device


def test_list_devices_maps_hostapi_names_and_defaults(fake_portaudio):
    devices = list_devices()
    assert len(devices) == len(fake_portaudio)
    wasapi_mic = devices[3]
    assert wasapi_mic.hostapi == "Windows WASAPI"
    assert wasapi_mic.is_default_input and not wasapi_mic.is_default_output
    assert devices[2].is_default_output and devices[2].hostapi == "MME"


def test_none_means_system_default(fake_portaudio):
    assert resolve_device(None, "input") is None


def test_valid_index_is_returned(fake_portaudio):
    assert resolve_device(6, "output") == 6


def test_unknown_index_raises(fake_portaudio):
    with pytest.raises(DeviceNotFoundError, match="index 99"):
        resolve_device(99, "input")


def test_index_of_wrong_direction_raises(fake_portaudio):
    with pytest.raises(DeviceNotFoundError, match="not an input device"):
        resolve_device(4, "input")


def test_name_prefers_wasapi_over_mme(fake_portaudio):
    # "bt-glasses" matches WASAPI 5 and MME 7 inputs; WASAPI wins.
    assert resolve_device("bt-glasses", "input") == 5


def test_one_glasses_spec_resolves_in_both_directions(fake_portaudio):
    # The real glasses: one "BT-Glasses" spec picks the mic for input and the
    # single shared endpoint for output.
    assert resolve_device("BT-Glasses", "input") == 5
    assert resolve_device("BT-GLASSES", "output") == 6


def test_hands_free_name_only_exists_under_wdm_ks(fake_portaudio):
    # Windows has no "Hands-Free" WASAPI/MME endpoint for the glasses.
    with pytest.raises(DeviceNotFoundError):
        resolve_device("Hands-Free", "output")


def test_exact_name_beats_lower_index(fake_portaudio):
    # "speakers" is a substring of device 4 and the exact name of device 11.
    assert resolve_device("Speakers", "output") == 11


def test_name_only_under_other_hostapis_is_not_found(fake_portaudio):
    with pytest.raises(DeviceNotFoundError, match="BT Headphones"):
        resolve_device("BT Headphones", "input")


def test_blank_name_raises(fake_portaudio):
    with pytest.raises(DeviceNotFoundError, match="empty"):
        resolve_device("  ", "input")
