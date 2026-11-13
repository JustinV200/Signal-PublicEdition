"""Tests for audiohub.tts.download: streamed, atomic downloads with progress.

urllib's urlopen is replaced with fakes, so no test touches the network.
"""

import http.client
import io
import urllib.error
from pathlib import Path

import pytest

from audiohub.tts import ModelDownloadError
from audiohub.tts.download import PARTIAL_SUFFIX, download_file

URL = "https://example.com/model.onnx"


class FakeResponse(io.BytesIO):
    """A urlopen response: a readable body plus the headers the server sent."""

    def __init__(self, body: bytes, content_length: int | None) -> None:
        super().__init__(body)
        self.headers = {} if content_length is None else {"Content-Length": str(content_length)}


class FailingResponse(FakeResponse):
    """A response that raises `error` on the read after the first chunk."""

    def __init__(self, body: bytes, error: Exception) -> None:
        super().__init__(body, len(body) * 2)
        self.error = error
        self.reads = 0

    def read(self, size: int | None = -1) -> bytes:
        self.reads += 1
        if self.reads > 1:
            raise self.error
        return super().read(size)


def serve(monkeypatch: pytest.MonkeyPatch, response: FakeResponse) -> list[str]:
    """Make urlopen return `response`, and record the URLs requested."""
    requested: list[str] = []

    def fake_urlopen(url: str, timeout: float) -> FakeResponse:
        requested.append(url)
        return response

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return requested


def partial_of(destination: Path) -> Path:
    return destination.with_name(destination.name + PARTIAL_SUFFIX)


def test_downloads_body_to_destination(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    body = b"model-bytes" * 1000
    requested = serve(monkeypatch, FakeResponse(body, len(body)))
    destination = tmp_path / "model.onnx"

    download_file(URL, destination)

    assert requested == [URL]
    assert destination.read_bytes() == body
    assert not partial_of(destination).exists()


def test_downloads_without_content_length(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    serve(monkeypatch, FakeResponse(b"abc", None))
    destination = tmp_path / "voices.bin"

    download_file(URL, destination)

    assert destination.read_bytes() == b"abc"
    assert "MB" in capsys.readouterr().err


def test_short_body_raises_and_leaves_no_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    serve(monkeypatch, FakeResponse(b"half", 8))
    destination = tmp_path / "model.onnx"

    with pytest.raises(ModelDownloadError, match="4 of 8 bytes"):
        download_file(URL, destination)

    assert not destination.exists()
    assert not partial_of(destination).exists()


def test_network_error_is_wrapped_with_the_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def refuse(url: str, timeout: float) -> FakeResponse:
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr("urllib.request.urlopen", refuse)

    with pytest.raises(ModelDownloadError, match=URL) as raised:
        download_file(URL, tmp_path / "model.onnx")

    assert isinstance(raised.value.__cause__, urllib.error.URLError)


@pytest.mark.parametrize(
    "error",
    [
        ConnectionResetError("connection dropped"),
        # An HTTPException, not an OSError, so it needs catching separately.
        http.client.IncompleteRead(b"xx", 8),
    ],
)
def test_mid_stream_failure_is_wrapped_and_removes_the_partial_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, error: Exception
) -> None:
    serve(monkeypatch, FailingResponse(b"x" * 10, error))
    destination = tmp_path / "model.onnx"

    with pytest.raises(ModelDownloadError, match=URL) as raised:
        download_file(URL, destination)

    assert raised.value.__cause__ is error
    assert not destination.exists()
    assert not partial_of(destination).exists()


def test_failed_download_keeps_an_existing_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "model.onnx"
    destination.write_bytes(b"old")
    serve(monkeypatch, FakeResponse(b"ne", 3))

    with pytest.raises(ModelDownloadError):
        download_file(URL, destination)

    assert destination.read_bytes() == b"old"
