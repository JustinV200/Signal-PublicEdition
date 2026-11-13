"""Tests for whiteboard.config: the example file matches the code defaults, bad values fail."""

import pytest

from whiteboard.config import TOOL_ROOT, ConfigError, Settings, load_settings, settings_from_dict


def test_example_file_matches_code_defaults() -> None:
    assert load_settings(TOOL_ROOT / "whiteboard.example.toml") == Settings()


def test_override_keeps_other_defaults() -> None:
    settings = settings_from_dict({"display": {"port": 9000}})
    assert settings.display.port == 9000
    assert settings.display.name_match == "PROJ-1"


@pytest.mark.parametrize(
    "data",
    [
        {"display": {"port": 0}},
        {"camera": {"backend": "v4l2"}},
        {"watcher": {"sample_s": "fast"}},
        {"display": {"nope": 1}},
        {"projector": {}},
    ],
)
def test_bad_values_raise_config_error(data: dict) -> None:
    with pytest.raises(ConfigError):
        settings_from_dict(data)
