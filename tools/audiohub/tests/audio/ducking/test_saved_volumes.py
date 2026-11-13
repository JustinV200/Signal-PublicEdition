"""Tests for audiohub.audio.ducking.saved_volumes: the crash-safety state file."""

import pytest

from audiohub.audio.ducking.saved_volumes import SavedVolume, load_saved_volumes, save_volumes


def test_save_then_load_round_trips_and_creates_the_folder(tmp_path):
    path = tmp_path / ".cache" / "ducking.json"
    volumes = {"Spotify.exe": SavedVolume(0.8, 0.12), "chrome.exe": SavedVolume(0.4, 0.06)}
    save_volumes(path, volumes)
    assert load_saved_volumes(path) == volumes


def test_missing_file_means_nothing_to_restore(tmp_path):
    assert load_saved_volumes(tmp_path / "absent.json") == {}


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        '{"Spotify.exe": [{"original": 0.8, "ducked": 0.2}]}',
        '{"Spotify.exe": {"original": 1.5, "ducked": 0.2}}',
        '{"Spotify.exe": {"original": NaN, "ducked": 0.2}}',
    ],
)
def test_invalid_file_is_ignored_and_deleted(tmp_path, text):
    path = tmp_path / "ducking.json"
    path.write_text(text)
    assert load_saved_volumes(path) == {}
    assert not path.exists()


def test_unwritable_location_is_logged_not_raised(tmp_path, caplog):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where the folder should be")
    save_volumes(blocker / "ducking.json", {"Spotify.exe": SavedVolume(0.8, 0.12)})
    assert "could not save ducking state" in caplog.text
