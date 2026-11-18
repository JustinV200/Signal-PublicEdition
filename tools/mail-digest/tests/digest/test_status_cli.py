"""`mail-digest status`: the setup tool's health check, read from the state file."""

from pathlib import Path

import pytest

from mail_digest.digest.status_cli import EXIT_FAILED, EXIT_OK, status_summary


@pytest.mark.parametrize(
    ("state_text", "code", "words_start"),
    [
        (None, EXIT_OK, "set up, no run yet"),
        ('{"failures": 0}', EXIT_OK, "last run worked ("),
        ('{"failures": 2}', EXIT_FAILED, "the last 2 runs failed ("),
        ("not json", EXIT_FAILED, "its state file is unreadable"),
    ],
)
def test_status_summary(tmp_path: Path, state_text, code, words_start) -> None:
    state_path = tmp_path / "state.json"
    if state_text is not None:
        state_path.write_text(state_text, encoding="utf-8")

    exit_code, summary = status_summary(state_path)

    assert (exit_code, summary["words"][: len(words_start)]) == (code, words_start)
    # Read-only: a corrupt file is never copied aside or rewritten.
    assert [p.name for p in tmp_path.iterdir()] == ([] if state_text is None else ["state.json"])
