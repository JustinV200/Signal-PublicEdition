"""Parsing the voice hub's status lines into its phase and voice-feed events."""

import pytest

from signal_console.status import HubLine, parse_hub_line


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("[14:02:10.0] listening", HubLine("listening", None, "")),
        (
            '[14:02:15.2] heard: "Hey Claude, what\'s "x" (now)?" (2.1 s audio, stt 85 ms)\n',
            HubLine(None, "heard", 'Hey Claude, what\'s "x" (now)?'),
        ),
        (
            "[14:02:16.0] speaking: \"It's two: o'clock...\" (+1 more) (kernel 12 ms)",
            HubLine("speaking", "said", "It's two: o'clock..."),
        ),
        (
            "[14:02:20.0] barge-in: cut Claude off",
            HubLine(None, "note", "barge-in: cut Claude off"),
        ),
        ("[14:02:21.0] ignored: no wake phrase", HubLine(None, "ignored", "no wake phrase")),
        (
            "2026-10-23 07:00:50,211 ERROR audiohub.loop.voice_output: could not play a chunk",
            HubLine(None, "note", "error: could not play a chunk"),
        ),
        ("2026-10-19 14:02:22,000 INFO audiohub: something", None),
    ],
)
def test_parse_hub_line(line, expected):
    assert parse_hub_line(line) == expected
