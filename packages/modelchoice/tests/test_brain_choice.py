"""Tests for read_brain_choice: only listed values get through."""

from pathlib import Path

import pytest

from signal_modelchoice import BrainChoice, read_brain_choice


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"model": "opus", "effort": "high"}', BrainChoice("opus", "high")),
        # An unknown value is ignored on its own; the other one still counts.
        ('{"model": "claude-opus --dangerously", "effort": "high"}', BrainChoice(None, "high")),
        ('{"model": "sonnet", "effort": "max"}', BrainChoice("sonnet", None)),
        ('{"model": 7}', BrainChoice()),
        ("not json", BrainChoice()),
        ('["opus", "high"]', BrainChoice()),
        ("[" * 3000, BrainChoice()),  # too deep for the parser: read as unset, not a crash
        (None, BrainChoice()),
    ],
)
def test_read_brain_choice_keeps_only_listed_values(
    tmp_path: Path, content: str | None, expected: BrainChoice
) -> None:
    path = tmp_path / "brain-choice.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert read_brain_choice(path) == expected
