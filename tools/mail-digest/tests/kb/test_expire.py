"""Tests for mail_digest.kb.expire: expired temporary notes go, current and undated stay."""

from datetime import date

from mail_digest.kb import expire_notes

TODAY = date(2026, 10, 23)


def test_removes_only_expired_dated_notes_and_keeps_line_endings(tmp_path, monkeypatch):
    path = tmp_path / "README.md"
    path.write_bytes(
        b"# Course\r\n"
        b"Watch for (until 2026-10-22): old\r\n"
        b"Watch for (until 2026-10-23): today\r\n"
        b"Watch for (until 2026-99-99): bad date\r\n"
        b"Watch for: undated\r\n"
        b"tail\r\n"
    )
    removed = expire_notes(tmp_path, ["README.md"], TODAY)
    assert removed == ["Watch for (until 2026-10-22): old"]
    assert path.read_bytes() == (
        b"# Course\r\n"
        b"Watch for (until 2026-10-23): today\r\n"
        b"Watch for (until 2026-99-99): bad date\r\n"
        b"Watch for: undated\r\n"
        b"tail\r\n"
    )


def test_missing_file_is_skipped(tmp_path):
    assert expire_notes(tmp_path, ["gone.md"], TODAY) == []
