"""Tests for audiohub.audio.device_names: friendly names and Bluetooth hints."""

from dataclasses import dataclass

from audiohub.audio import BLUETOOTH, HANDS_FREE, bluetooth_hints
from audiohub.audio.device_names import friendly_device_name


@dataclass
class NamedDevice:
    index: int
    name: str


def test_wdm_ks_resource_string_is_expanded():
    raw = "Headset (@System32\\drivers\\bthhfenum.sys,#2;%1 Hands-Free%0\r\n;(BT-Glasses-01))"
    assert friendly_device_name(raw) == "Headset (BT-Glasses-01 Hands-Free)"


def test_stray_whitespace_is_collapsed():
    assert friendly_device_name("Mic  (X)\r\n") == "Mic (X)"


def test_hands_free_and_sibling_stereo_endpoint_are_hinted():
    devices = [
        NamedDevice(0, "Headset (BT-Glasses-01 Hands-Free)"),
        NamedDevice(1, "Headphones (BT-Glasses-01)"),
        NamedDevice(2, "Headphones (Realtek USB2.0 Audio)"),
    ]
    assert bluetooth_hints(devices) == {0: HANDS_FREE, 1: BLUETOOTH}


def test_windows_headset_form_name_counts_as_hands_free():
    assert bluetooth_hints([NamedDevice(0, "Headset (BT-Glasses-01)")]) == {0: HANDS_FREE}


def test_wired_usb_headset_is_not_hinted():
    devices = [
        NamedDevice(0, "Speakers (USB Wired Headset)"),
        NamedDevice(1, "Headset Microphone (HyperX Cloud)"),
    ]
    assert bluetooth_hints(devices) == {}


def test_truncated_mme_stereo_name_still_matches_its_headset():
    devices = [
        NamedDevice(0, "Headset (BT-Glasses-01 Hands-Free)"),
        NamedDevice(1, "Headphones (BT-Glasses-01 Stereo"),
    ]
    assert bluetooth_hints(devices)[1] == BLUETOOTH
