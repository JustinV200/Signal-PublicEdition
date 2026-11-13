"""iter_jpeg_parts: read the JPEG frames out of the daemon's MJPEG camera stream.

The daemon (daemon/camera_stream.py) sends `multipart/x-mixed-replace` parts, each
with a Content-Length header, so a part is read by its length instead of scanning
for the boundary. Standard library only, like the rest of this package.
"""

from collections.abc import Iterator
from typing import BinaryIO

from whiteboard.daemon_client.http_api import DaemonApiError

# readline's cap per header line, so a stream with no newlines can't fill memory.
# Our headers are far shorter; a longer line is just split and its pieces ignored.
MAX_HEADER_LINE_BYTES = 1024
# A 960 px JPEG is well under 1 MB; anything near this is a broken stream.
MAX_PART_BYTES = 8 * 1024 * 1024
CONTENT_LENGTH = b"content-length"


def iter_jpeg_parts(stream: BinaryIO) -> Iterator[bytes]:
    """Yield each part's JPEG bytes until the stream ends.

    Args:
        stream: The open response from DaemonApi.open_camera_stream().

    Raises:
        DaemonApiError: A part has a missing, bad or oversized Content-Length.
        TimeoutError: No data within the stream's timeout.
    """
    while True:
        length = _read_part_length(stream)
        if length is None:
            return
        jpeg = stream.read(length)
        if len(jpeg) < length:
            # The daemon stopped mid-frame (shutting down); not worth an error.
            return
        yield jpeg


def _read_part_length(stream: BinaryIO) -> int | None:
    """Skip to the end of the next part's headers and return its Content-Length.

    Returns:
        The length, or None at the end of the stream.
    """
    length: int | None = None
    while True:
        raw_line = stream.readline(MAX_HEADER_LINE_BYTES)
        if not raw_line:
            return None
        line = raw_line.strip()
        if not line:
            # A blank line: the CRLF after a frame, or the end of this part's headers.
            if length is not None:
                return length
            continue
        name, _, value = line.partition(b":")
        if name.strip().lower() == CONTENT_LENGTH:
            length = _parse_length(value)


def _parse_length(value: bytes) -> int:
    """A Content-Length value as a positive int under MAX_PART_BYTES. Raises DaemonApiError."""
    try:
        length = int(value.strip())
    except ValueError as error:
        raise DaemonApiError("camera stream sent a bad Content-Length") from error
    if not 0 < length <= MAX_PART_BYTES:
        raise DaemonApiError(f"camera stream sent an unlikely frame size: {length} bytes")
    return length
