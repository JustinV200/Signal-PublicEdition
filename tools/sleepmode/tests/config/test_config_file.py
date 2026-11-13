"""Tests for reading [lighting] and [input] from sleepmode.toml."""

from pathlib import Path

import pytest

from sleepmode.config import (
    ConfigError,
    InputSettings,
    LightingSettings,
    load_input_settings,
    load_lighting_settings,
)


def test_lighting_settings_are_read_and_bad_shapes_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sleepmode.toml"
    assert load_lighting_settings(path) == LightingSettings()  # no file: the defaults
    path.write_text('[lighting]\nenabled = false\noff_commands = [["a", "-x"]]\n', "utf-8")
    assert load_lighting_settings(path) == LightingSettings(False, "", (("a", "-x"),), ())
    # A command must be an argv list: a bare string would need a shell to split it.
    for bad in ('off_commands = ["a -x"]', "off_commands = [[]]", "enable = true"):
        path.write_text(f"[lighting]\n{bad}\n", "utf-8")
        with pytest.raises(ConfigError):
            load_lighting_settings(path)


def test_input_settings_are_read_and_bad_values_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sleepmode.toml"
    assert load_input_settings(path) == InputSettings()  # no file: the defaults
    path.write_text("[lighting]\nenabled = false\n[input]\nmouse_move_px = 250\n", "utf-8")
    assert load_input_settings(path) == InputSettings(250.0, 1.5)
    assert not load_lighting_settings(path).enabled  # [input] doesn't upset [lighting]
    bad_values = (
        "mouse_move_px = 0",
        "mouse_move_px = nan",
        "mouse_move_window_s = inf",
        "mouse_move_window_s = true",
        "move_px = 100",
    )
    for bad in bad_values:
        path.write_text(f"[input]\n{bad}\n", "utf-8")
        with pytest.raises(ConfigError):
            load_input_settings(path)
