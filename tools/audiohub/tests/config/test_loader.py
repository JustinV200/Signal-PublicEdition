"""Tests for audiohub.config.loader: reading TOML files into validated Settings."""

from pathlib import Path

import pytest

from audiohub.config import TOOL_ROOT, ConfigError, Settings, load_settings, loader


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "audiohub.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_default_file_gives_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "DEFAULT_CONFIG_PATH", tmp_path / "absent.toml")
    assert load_settings() == Settings()


def test_default_file_is_read_when_present(tmp_path, monkeypatch):
    path = write_config(tmp_path, "[tts]\nvoice = 'bm_lewis'\n")
    monkeypatch.setattr(loader, "DEFAULT_CONFIG_PATH", path)
    assert load_settings().tts.voice == "bm_lewis"


def test_explicit_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_settings(tmp_path / "nope.toml")


def test_partial_file_keeps_other_defaults(tmp_path):
    settings = load_settings(write_config(tmp_path, "[ducking]\nlevel = 0.3\n"))
    assert settings.ducking.level == 0.3
    assert settings.ducking.processes == ("Spotify.exe",)
    assert settings.stt == Settings().stt


def test_lists_become_tuples_and_ints_become_floats(tmp_path):
    text = "[wake]\nphrases = ['ok claude']\nfollow_up_s = 5\n"
    settings = load_settings(write_config(tmp_path, text))
    assert settings.wake.phrases == ("ok claude",)
    assert settings.wake.follow_up_s == 5.0
    assert isinstance(settings.wake.follow_up_s, float)


def test_invalid_toml_raises_with_path(tmp_path):
    path = write_config(tmp_path, "[ducking\nlevel = 1\n")
    with pytest.raises(ConfigError, match="invalid TOML") as error:
        load_settings(path)
    assert str(path) in str(error.value)


def test_unknown_section_raises(tmp_path):
    with pytest.raises(ConfigError, match="unknown section.*speaker"):
        load_settings(write_config(tmp_path, "[speaker]\nvolume = 1\n"))


def test_unknown_key_raises_and_lists_valid_keys(tmp_path):
    with pytest.raises(ConfigError, match=r"\[ducking\] unknown key\(s\): levle.*Valid keys"):
        load_settings(write_config(tmp_path, "[ducking]\nlevle = 0.2\n"))


def test_section_that_is_not_a_table_raises(tmp_path):
    with pytest.raises(ConfigError, match=r"\[ipc\] must be a table"):
        load_settings(write_config(tmp_path, "ipc = 3\n"))


def test_wrong_type_names_the_key(tmp_path):
    with pytest.raises(ConfigError, match="ipc.port: expected int, got str"):
        load_settings(write_config(tmp_path, "[ipc]\nport = '8765'\n"))


def test_out_of_range_value_raises(tmp_path):
    with pytest.raises(ConfigError, match="ducking.level: 1.5 is above the maximum"):
        load_settings(write_config(tmp_path, "[ducking]\nlevel = 1.5\n"))


def test_unknown_music_backend_raises(tmp_path):
    with pytest.raises(ConfigError, match="music.backend: 'winamp' is not one of auto"):
        load_settings(write_config(tmp_path, "[music]\nbackend = 'winamp'\n"))


def test_example_config_matches_code_defaults():
    # Keeps audiohub.example.toml and settings.py from drifting apart.
    assert load_settings(TOOL_ROOT / "audiohub.example.toml") == Settings()


def test_non_utf8_file_raises_config_error(tmp_path):
    path = tmp_path / "audiohub.toml"
    path.write_bytes(b"[tts]\nvoice = '\xff'\n")
    with pytest.raises(ConfigError, match="not valid UTF-8"):
        load_settings(path)
