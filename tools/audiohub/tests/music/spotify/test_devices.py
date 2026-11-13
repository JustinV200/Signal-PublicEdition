"""Tests for audiohub.music.spotify.devices: choosing an idle device to wake."""

import pytest

from audiohub.music.spotify.devices import pick_device_id


def device(device_id, device_type="Smartphone", *, is_restricted=False, name="") -> dict:
    return {"id": device_id, "type": device_type, "is_restricted": is_restricted, "name": name}


def test_computer_is_preferred_over_earlier_devices():
    response = {
        "devices": [device("phone"), device("speaker", "Speaker"), device("pc", "Computer")]
    }
    assert pick_device_id(response) == "pc"


def test_restricted_and_id_less_devices_are_skipped():
    response = {
        "devices": [
            device("pc", "Computer", is_restricted=True),
            {"type": "Computer", "id": None},
            device("phone"),
        ]
    }
    assert pick_device_id(response) == "phone"


@pytest.mark.parametrize("response", [None, {}, {"devices": None}, {"devices": [None, "x"]}])
def test_no_usable_device_gives_none(response):
    assert pick_device_id(response) is None


def test_hostname_match_beats_other_computers_case_insensitively():
    response = {
        "devices": [
            device("laptop", "Computer", name="LAPTOP"),
            device("pc", "Computer", name="Desktop-Example"),
        ]
    }
    assert pick_device_id(response, "DESKTOP-EXAMPLE") == "pc"


def test_unmatched_hostname_falls_back_to_computer():
    response = {"devices": [device("phone"), device("laptop", "Computer", name="LAPTOP")]}
    assert pick_device_id(response, "DESKTOP-EXAMPLE") == "laptop"
