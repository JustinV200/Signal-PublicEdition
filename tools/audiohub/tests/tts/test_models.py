"""Tests for audiohub.tts.models: finding or downloading the Kokoro files.

download_file is replaced with a fake that writes a stub file, so no test
touches the network.
"""

from pathlib import Path

import pytest

from audiohub.tts import ensure_models
from audiohub.tts.models import MODEL_FILENAME, RELEASE_URL, VOICES_FILENAME


def fake_downloads(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Path]]:
    """Replace download_file with a stub writer and return the calls it gets."""
    calls: list[tuple[str, Path]] = []

    def fake_download_file(url: str, destination: Path) -> None:
        calls.append((url, destination))
        destination.write_bytes(b"stub")

    monkeypatch.setattr("audiohub.tts.models.download_file", fake_download_file)
    return calls


def test_downloads_both_files_when_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = fake_downloads(monkeypatch)

    model_path, voices_path = ensure_models(tmp_path)

    assert model_path == tmp_path / MODEL_FILENAME
    assert voices_path == tmp_path / VOICES_FILENAME
    assert calls == [
        (f"{RELEASE_URL}/{MODEL_FILENAME}", model_path),
        (f"{RELEASE_URL}/{VOICES_FILENAME}", voices_path),
    ]


def test_skips_files_that_already_exist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = fake_downloads(monkeypatch)
    (tmp_path / MODEL_FILENAME).write_bytes(b"model")
    (tmp_path / VOICES_FILENAME).write_bytes(b"voices")

    model_path, voices_path = ensure_models(tmp_path)

    assert calls == []
    assert model_path.read_bytes() == b"model"
    assert voices_path.read_bytes() == b"voices"


def test_downloads_only_the_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = fake_downloads(monkeypatch)
    (tmp_path / MODEL_FILENAME).write_bytes(b"model")

    ensure_models(tmp_path)

    assert [destination.name for _, destination in calls] == [VOICES_FILENAME]


def test_creates_the_models_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_downloads(monkeypatch)
    models_dir = tmp_path / "nested" / "models"

    model_path, _ = ensure_models(models_dir)

    assert model_path.parent == models_dir
    assert model_path.is_file()
