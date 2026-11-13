"""Tests for the console status line helpers."""

import io
from datetime import datetime

from audiohub.loop import StatusLine

FIXED_TIME = datetime(2026, 10, 19, 14, 2, 15, 234000)


def _status(stream=None):
    stream = stream or io.StringIO()
    return StatusLine(stream, clock=lambda: FIXED_TIME), stream


def test_show_prints_timestamped_label_and_detail():
    status, stream = _status()
    status.show("heard", '"hello"')
    status.show("listening")
    assert stream.getvalue() == '[14:02:15.2] heard: "hello"\n[14:02:15.2] listening\n'


def test_repeated_line_is_printed_once():
    status, stream = _status()
    status.show("listening")
    status.show("listening")
    status.show("thinking")
    status.show("listening")
    assert stream.getvalue().count("listening") == 2


def test_unencodable_characters_are_replaced():
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", newline="\n")
    status, _ = _status(stream)
    status.show("speaking", "done \U0001f600")
    stream.flush()
    assert raw.getvalue().decode("cp1252").endswith("speaking: done ?\n")
