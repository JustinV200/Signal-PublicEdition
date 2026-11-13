"""Tests for the error log: it records what failed, never the input that failed."""

from usage.error_log import log_error


def test_log_has_the_error_type_and_message_but_not_the_input(tmp_path):
    log_file = tmp_path / "errors.log"
    # A UnicodeDecodeError's repr holds the bytes it failed on.
    error = UnicodeDecodeError("utf-8", b"private prompt text \xff", 20, 21, "invalid start byte")
    log_error(log_file, "hook", error)
    line = log_file.read_text(encoding="utf-8")
    assert "hook UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff" in line
    assert "private" not in line
