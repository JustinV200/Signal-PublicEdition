"""Merging the password-saving prefs into a profile's Preferences file."""

import json

import pytest

from browser_tool.backends import disable_password_saving


def test_existing_prefs_are_kept_and_overridden_where_needed(tmp_path):
    preferences = tmp_path / "Default" / "Preferences"
    preferences.parent.mkdir()
    preferences.write_text(
        json.dumps({"credentials_enable_service": True, "autofill": {"other": 1}, "theme": "x"})
    )
    merged = json.loads(disable_password_saving(tmp_path).read_text())
    assert merged["credentials_enable_service"] is False
    assert merged["autofill"]["other"] == 1
    assert merged["autofill"]["profile_enabled"] is False
    assert merged["theme"] == "x"


def test_corrupt_preferences_are_left_alone_and_reported(tmp_path):
    preferences = tmp_path / "Default" / "Preferences"
    preferences.parent.mkdir()
    preferences.write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        disable_password_saving(tmp_path)
    assert preferences.read_text() == "{not json"
