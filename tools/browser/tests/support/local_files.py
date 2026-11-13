"""Helpers for the local-file tests: a guard that fails on any disk access, and a tiny PDF."""

import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

OS_PATH_CALLS = ("realpath", "exists", "isdir", "isfile")
OS_CALLS = ("lstat", "stat", "open", "scandir")


@contextmanager
def no_disk(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Within the block, any filesystem call fails the test (for checks that must be lexical)."""

    def touched(*args, **kwargs):
        raise AssertionError("touched the filesystem")

    with monkeypatch.context() as patched:
        for name in OS_PATH_CALLS:
            patched.setattr(os.path, name, touched)
        for name in OS_CALLS:
            patched.setattr(os, name, touched)
        yield


def make_pdf(page_texts: list[str]) -> bytes:
    """A valid PDF with one page per text (ASCII, no parentheses), built by hand."""
    # Objects 1-3: the catalog, the page tree (filled in below) and the font.
    font = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", "", font]
    kids = []
    for text in page_texts:
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {len(objects)} 0 R "
            "/Resources << /Font << /F1 3 0 R >> >> >>"
        )
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(page_texts)} >>"
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    return out + f"startxref\n{xref_at}\n%%EOF\n".encode()
