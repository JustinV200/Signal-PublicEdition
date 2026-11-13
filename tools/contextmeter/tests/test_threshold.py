"""Tests for reading the handoff threshold from AGENTS.md."""

import pytest

from contextmeter.threshold import handoff_threshold


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("When you reach **60% of your context window**, stop.", 60),
        (
            "reach **<!-- setting:context-handoff-percent -->65<!-- /setting -->% of your"
            " context window**",
            65,
        ),
        ("No threshold line here.", 75),
        ("reach **0% of your context window**", 75),
        (None, 75),  # missing file
    ],
)
def test_handoff_threshold(tmp_path, text, expected):
    agents_md = tmp_path / "AGENTS.md"
    if text is not None:
        agents_md.write_text(text, encoding="utf-8")
    assert handoff_threshold(agents_md) == expected
