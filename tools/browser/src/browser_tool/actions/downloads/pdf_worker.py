"""Child process for pdf_text.py: extract text from one PDF with pypdf, under a time limit.

Run as a script (python -I pdf_worker.py FIRST LAST MAX_CHARS TIMEOUT_S), never
imported: a malicious PDF can make pypdf slow or crash, and a child process
keeps that out of the MCP server. The PDF's bytes come on stdin; one JSON
object goes to stdout:
- {"total": N, "pages": [text, ...], "cut": bool}: the text of pages FIRST to
  LAST (1-based, clipped to the PDF), stopping once MAX_CHARS are collected,
  and each page's text cut at MAX_CHARS + PAGE_MARGIN_CHARS so one huge page
  can't make a huge reply (the margin keeps any secret that straddles
  MAX_CHARS whole, for the parent to scrub before its own cut; in theory a
  scrub that shrinks the text a lot could pull the parent's cut point earlier);
- {"error": "encrypted"} or {"error": "unreadable"}, never pypdf's own message,
  which can quote the file.
A watchdog thread exits the process after TIMEOUT_S. It is a backup: the
parent kills the child (on Windows the venv launcher's job object takes this
interpreter down with it) once its own deadline passes.
"""

import io
import json
import os
import sys
import threading

from pypdf import PdfReader

TIMED_OUT_EXIT_CODE = 3
# Longer than any secret the parent's scrub must still see whole.
PAGE_MARGIN_CHARS = 1000


def extract(data: bytes, first: int, last: int, max_chars: int) -> dict[str, object]:
    """The JSON reply for pages `first`..`last` of the PDF in `data` (module docstring)."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            return {"error": "encrypted"}
        total = len(reader.pages)
        texts: list[str] = []
        collected = 0
        for index in range(first - 1, min(last, total)):
            text = reader.pages[index].extract_text() or ""
            is_page_cut = len(text) > max_chars + PAGE_MARGIN_CHARS
            texts.append(text[: max_chars + PAGE_MARGIN_CHARS])
            collected += len(text)
            if is_page_cut or collected >= max_chars:
                return {"total": total, "pages": texts, "cut": True}
        return {"total": total, "pages": texts, "cut": False}
    except Exception:  # noqa: BLE001 - any pypdf failure is just "unreadable"; never echo it
        return {"error": "unreadable"}


def main() -> None:
    """Read the arguments and stdin, start the watchdog, print the reply."""
    first, last, max_chars = (int(value) for value in sys.argv[1:4])
    timer = threading.Timer(float(sys.argv[4]), os._exit, args=(TIMED_OUT_EXIT_CODE,))
    timer.daemon = True
    timer.start()
    reply = extract(sys.stdin.buffer.read(), first, last, max_chars)
    sys.stdout.write(json.dumps(reply))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
