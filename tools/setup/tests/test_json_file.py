"""update_json_file refuses a file it can't merge and never overwrites another writer's save."""

import json
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pytest

from signal_setup.wiring import WiringError
from signal_setup.wiring.json_file import update_json_file


def _add_key(settings: dict[str, Any]) -> dict[str, Any]:
    """A merge that always changes something."""
    return {**settings, "added": True}


@pytest.mark.parametrize("text", ["{not json", "[1, 2]", ""])
def test_refuses_a_file_that_is_not_a_json_object(tmp_path: Path, text: str) -> None:
    path, backup = tmp_path / "settings.json", tmp_path / "backup.json"
    path.write_text(text)
    with pytest.raises(WiringError) as refused:
        update_json_file(path, backup, _add_key)
    assert path.read_text() == text and not backup.exists()
    assert "\n" not in str(refused.value)  # one sentence for the user, not a traceback


@pytest.mark.parametrize(
    ("changes", "outcome", "expected"),
    [
        # Changed once: the retry merges onto the other writer's version.
        (1, nullcontext(), {"model": "sonnet", "write": 1, "added": True}),
        # Changed every time: refused, and the file is as the other writer left it.
        (2, pytest.raises(WiringError), {"model": "sonnet", "write": 2}),
    ],
)
def test_a_file_changed_before_the_replace_is_not_overwritten(
    tmp_path: Path, changes: int, outcome: Any, expected: dict[str, Any]
) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"model": "opus"}')
    reads = 0

    def merge_while_another_writer_saves(settings: dict[str, Any]) -> dict[str, Any]:
        nonlocal reads
        reads += 1
        if reads <= changes:  # lands after setup's read, before its re-read
            path.write_text(json.dumps({"model": "sonnet", "write": reads}))
        return _add_key(settings)

    with outcome:
        update_json_file(path, tmp_path / "backup.json", merge_while_another_writer_saves)
    assert json.loads(path.read_text()) == expected
