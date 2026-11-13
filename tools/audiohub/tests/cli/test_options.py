"""Tests for audiohub.cli.options: device spec parsing and settings overrides."""

import argparse

import pytest

from audiohub.cli.options import apply_device_overrides, parse_device_spec
from audiohub.config import AudioSettings, Settings


@pytest.mark.parametrize(
    ("text", "expected"),
    [("15", 15), (" 3 ", 3), ("Hands-Free", "Hands-Free"), ("BT-Glasses-01", "BT-Glasses-01")],
)
def test_digits_are_indexes_and_anything_else_is_a_name(text, expected):
    assert parse_device_spec(text) == expected


def test_non_ascii_digits_stay_a_name():
    assert parse_device_spec("١") == "١"


def test_empty_device_spec_is_rejected():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_device_spec("")


def test_overrides_replace_only_the_given_devices():
    settings = Settings(audio=AudioSettings(input_device="mic", output_device="out"))
    updated = apply_device_overrides(settings, None, 7)
    assert updated.audio == AudioSettings(input_device="mic", output_device=7)
    assert settings.audio.output_device == "out"
