"""Download one file over HTTP(S) with a progress line and an atomic finish.

Used by `models.ensure_models` to fetch the Kokoro model files. The file is
streamed to `<name>.part` beside the destination and only renamed into place
once every byte has arrived, so an interrupted download never leaves a
truncated file that later looks complete.
"""

import os
import sys
import urllib.request
from http.client import HTTPException, HTTPResponse
from pathlib import Path
from typing import BinaryIO

CHUNK_BYTES = 1024 * 1024
TIMEOUT_S = 30
PARTIAL_SUFFIX = ".part"
BYTES_PER_MB = 1024 * 1024


class ModelDownloadError(RuntimeError):
    """A model file could not be downloaded completely."""


def download_file(url: str, destination: Path) -> None:
    """Download `url` to `destination`, printing progress to stderr.

    Args:
        url: The HTTP(S) URL to fetch.
        destination: The final path. Its parent directory must exist.

    Raises:
        ModelDownloadError: On a network or HTTP error, or when fewer bytes
            arrive than the server announced. The partial file is removed.
    """
    partial = destination.with_name(destination.name + PARTIAL_SUFFIX)
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
            total_bytes = _content_length(response)
            with partial.open("wb") as sink:
                received = _stream(response, sink, destination.name, total_bytes)
        if total_bytes is not None and received != total_bytes:
            raise ModelDownloadError(
                f"Download of {url} stopped at {received} of {total_bytes} bytes"
            )
        os.replace(partial, destination)
    except (OSError, HTTPException) as error:
        # URLError and HTTPError are OSError subclasses, so OSError covers
        # network failures, HTTP error statuses and local disk errors.
        # HTTPException covers protocol failures such as IncompleteRead.
        raise ModelDownloadError(f"Could not download {url}: {error}") from error
    finally:
        # After a successful replace the partial file is already gone.
        partial.unlink(missing_ok=True)


def _content_length(response: HTTPResponse) -> int | None:
    """Return the announced body size, or None when the server didn't say."""
    header = response.headers.get("Content-Length")
    if header is None or not header.isdigit():
        return None
    return int(header)


def _stream(response: HTTPResponse, sink: BinaryIO, label: str, total_bytes: int | None) -> int:
    """Copy the response body into `sink` chunk by chunk, reporting progress.

    Returns:
        The number of bytes written.
    """
    received = 0
    last_reported = -1
    while chunk := response.read(CHUNK_BYTES):
        sink.write(chunk)
        received += len(chunk)
        last_reported = _report_progress(label, received, total_bytes, last_reported)
    print(file=sys.stderr)
    return received


def _report_progress(label: str, received: int, total_bytes: int | None, last_reported: int) -> int:
    """Rewrite the progress line when the whole percent (or MB) changes.

    Progress goes to stderr so it can never corrupt stdout, which the stdio
    MCP server uses for its protocol.

    Returns:
        The step just reported, or `last_reported` when nothing was printed.
    """
    received_mb = received / BYTES_PER_MB
    if total_bytes:
        step = received * 100 // total_bytes
        message = f"{step}% ({received_mb:.1f} / {total_bytes / BYTES_PER_MB:.1f} MB)"
    else:
        step = int(received_mb)
        message = f"{received_mb:.1f} MB"
    if step == last_reported:
        return last_reported
    print(f"\rDownloading {label}: {message}", end="", file=sys.stderr, flush=True)
    return step
