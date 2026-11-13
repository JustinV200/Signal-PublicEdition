"""Text out of a PDF's pages, through pdf_worker.py in a child process with a time limit.

pypdf is pure Python and a malicious PDF can make it slow or deep, so it never
runs in the server's process: the child gets the bytes on stdin, has
PDF_TIMEOUT_S (it also stops itself, see pdf_worker), and is killed if it runs
past that. Its stderr (pypdf warnings, which can quote the file) is dropped,
its reply is read only up to MAX_REPLY_BYTES (past that the child is killed),
and it is checked for shape before use. Callers only ever see the
fixed messages here.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from browser_tool.actions.errors import ActionError

WORKER_PATH = Path(__file__).with_name("pdf_worker.py")
PDF_TIMEOUT_S = 20.0
# Extra time for the child to start and reply before it is killed from here.
KILL_GRACE_S = 5.0
# pdf_worker.TIMED_OUT_EXIT_CODE (not imported: that module imports pypdf).
WORKER_TIMED_OUT_EXIT_CODE = 3
# A reply bigger than this is not a reply pdf_worker would send.
MAX_REPLY_BYTES = 8 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024
# No console window flashes up on Windows (0 elsewhere).
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

ENCRYPTED = "refused: the PDF is password-protected"
UNREADABLE = "refused: the PDF could not be read (damaged or not a PDF)"
TIMED_OUT = f"refused: reading the PDF took over {PDF_TIMEOUT_S:g} s, so it was stopped"


class PdfText(NamedTuple):
    """The text of some of a PDF's pages.

    Attributes:
        total_pages: How many pages the PDF has.
        pages: The text of each page read, in order, from the first one asked for.
        is_cut: True when reading stopped early at the character cap.
    """

    total_pages: int
    pages: list[str]
    is_cut: bool


async def pdf_text(data: bytes, first: int, last: int, max_chars: int) -> PdfText:
    """Extract pages `first`..`last` (1-based, inclusive) of the PDF in `data`.

    Args:
        data: The PDF's bytes.
        first: The first page to read.
        last: The last page to read (clipped to the PDF's length).
        max_chars: Stop reading pages once this much text is collected.

    Raises:
        ActionError: ENCRYPTED, UNREADABLE or TIMED_OUT.
    """
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",  # no PYTHONPATH, user site or current folder on the child's path
        str(WORKER_PATH),
        *(str(value) for value in (first, last, max_chars, PDF_TIMEOUT_S)),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        creationflags=NO_WINDOW,
    )
    try:
        output = await asyncio.wait_for(_exchange(process, data), PDF_TIMEOUT_S + KILL_GRACE_S)
    except TimeoutError:
        raise ActionError(TIMED_OUT) from None
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    if output is None:
        raise ActionError(UNREADABLE)
    if process.returncode != 0:
        raise ActionError(
            TIMED_OUT if process.returncode == WORKER_TIMED_OUT_EXIT_CODE else UNREADABLE
        )
    return _parse_reply(output)


async def _exchange(process: asyncio.subprocess.Process, data: bytes) -> bytes | None:
    """Send `data` to the child, then read its reply, stopping past MAX_REPLY_BYTES.

    Returns:
        The reply, or None when it is too big or the child quit before taking
        the PDF (the caller then kills the child if it is still running).
    """
    assert process.stdin is not None and process.stdout is not None
    try:
        process.stdin.write(data)
        await process.stdin.drain()
        process.stdin.close()
    except (BrokenPipeError, ConnectionResetError):
        return None  # the child quit before taking the PDF: unreadable

    output = bytearray()
    while chunk := await process.stdout.read(READ_CHUNK_BYTES):
        output += chunk
        if len(output) > MAX_REPLY_BYTES:
            return None
    await process.wait()
    return bytes(output)


def _parse_reply(output: bytes) -> PdfText:
    """Check the child's JSON reply and turn it into PdfText.

    Raises:
        ActionError: ENCRYPTED, or UNREADABLE for an error or a malformed reply.
    """
    try:
        reply = json.loads(output)
    except ValueError:
        raise ActionError(UNREADABLE) from None
    if not isinstance(reply, dict):
        raise ActionError(UNREADABLE)
    if reply.get("error") == "encrypted":
        raise ActionError(ENCRYPTED)
    total, pages, is_cut = reply.get("total"), reply.get("pages"), reply.get("cut")
    is_valid = (
        isinstance(total, int)
        and isinstance(is_cut, bool)
        and isinstance(pages, list)
        and all(isinstance(page, str) for page in pages)
    )
    if not is_valid:
        raise ActionError(UNREADABLE)
    return PdfText(total, pages, is_cut)
