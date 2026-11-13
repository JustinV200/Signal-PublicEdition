"""Tests for the atomic JSON writer."""

from signal_jsonstate import read_json_object, write_json_atomic


def test_write_creates_a_missing_state_folder(tmp_path) -> None:
    # Regression: the whiteboard's weather cache failed with "No such file or directory"
    # because its .state/idle folder didn't exist yet.
    path = tmp_path / ".state" / "idle" / "weather.json"
    write_json_atomic(path, {"temp_f": 51})
    assert read_json_object(path) == {"temp_f": 51}
    assert [p.name for p in path.parent.iterdir()] == ["weather.json"]  # no temp file left
