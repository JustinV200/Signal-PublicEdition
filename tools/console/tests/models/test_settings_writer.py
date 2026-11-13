"""The settings writer: only allowlisted keys and values; a refusal leaves the file as it was.

Everything runs on tmp copies, never the repo's .claude/settings.local.json.
"""

import json

import pytest

from signal_console.models import (
    SettingsFiles,
    SettingsWriteError,
    settings_writer,
    write_local_setting,
)

ORIGINAL = {"permissions": {"allow": ["Bash(git status)"]}, "model": "opus", "hooks": {}}


def _files(tmp_path, content):
    files = SettingsFiles(tmp_path / "settings.local.json", tmp_path / "state" / "backup.json")
    if content is not None:
        files.settings.write_text(content, encoding="utf-8")
    return files


@pytest.mark.parametrize(
    ("key", "value", "expected_change"),
    [
        ("effortLevel", "high", {"effortLevel": "high"}),
        ("model", "sonnet[1m]", {"model": "sonnet[1m]"}),
        ("model", None, {"model": None}),  # "use my user settings" removes the key
    ],
)
def test_allowed_pick_is_written_and_other_keys_survive(tmp_path, key, value, expected_change):
    original_text = json.dumps(ORIGINAL)
    files = _files(tmp_path, original_text)

    write_local_setting(files, key, value)

    expected = {**ORIGINAL, **expected_change}
    expected = {k: v for k, v in expected.items() if v is not None}
    assert json.loads(files.settings.read_text(encoding="utf-8")) == expected
    assert files.backup.read_text(encoding="utf-8") == original_text


@pytest.mark.parametrize(
    ("content", "key", "value"),
    [
        (json.dumps(ORIGINAL), "permissions", "x"),  # not an allowlisted key
        (json.dumps(ORIGINAL), "env", None),
        (json.dumps(ORIGINAL), "model", "claude-opus-5-5"),  # not a listed alias
        (json.dumps(ORIGINAL), "effortLevel", "max"),  # session-only, not for settings
        (None, "model", "opus"),  # missing: never created from {}
        ("{not json", "model", "opus"),
        ('["model"]', "model", "opus"),  # parses, but isn't an object
        ("[" * 3000, "model", "opus"),  # too deep for the parser
    ],
)
def test_refusals_leave_the_file_byte_identical(tmp_path, content, key, value):
    files = _files(tmp_path, content)

    with pytest.raises(SettingsWriteError, match="can't update settings"):
        write_local_setting(files, key, value)

    if content is None:
        assert not files.settings.exists()
    else:
        assert files.settings.read_text(encoding="utf-8") == content


def test_a_file_that_keeps_changing_before_the_replace_is_refused(tmp_path, monkeypatch):
    files = _files(tmp_path, json.dumps(ORIGINAL))
    real_back_up = settings_writer._back_up
    edits = []

    def back_up_then_claude_code_writes(backup, raw):
        real_back_up(backup, raw)
        # Claude Code lands a write between the first read and the re-read, every time.
        edits.append(json.dumps({**ORIGINAL, "edit": len(edits)}))
        files.settings.write_text(edits[-1], encoding="utf-8")

    monkeypatch.setattr(settings_writer, "_back_up", back_up_then_claude_code_writes)

    with pytest.raises(SettingsWriteError, match="kept changing"):
        write_local_setting(files, "effortLevel", "low")

    assert len(edits) == settings_writer.WRITE_ATTEMPTS  # it retried once
    assert files.settings.read_text(encoding="utf-8") == edits[-1]  # Claude Code's write stands
