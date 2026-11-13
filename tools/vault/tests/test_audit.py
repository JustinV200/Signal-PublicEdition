"""Audit log: one JSON line per event, model-supplied ids sanitised, write failures not fatal."""

import json

from vault.audit import EVENT_FILL, INVALID_ID_LABEL, AuditLog


def test_record_appends_a_line_and_sanitises_odd_ids(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    log = AuditLog(log_path)

    log.record(EVENT_FILL, "github", "filled", top_origin="https://github.com")
    log.record(EVENT_FILL, "x\n{injected}", "not_found")

    first, second = (json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines())
    assert first["credential_id"] == "github" and first["top_origin"] == "https://github.com"
    assert second["credential_id"] == INVALID_ID_LABEL


def test_a_failed_write_warns_instead_of_raising(tmp_path, caplog):
    blocked_path = tmp_path / "is-a-directory"
    blocked_path.mkdir()

    AuditLog(blocked_path).record(EVENT_FILL, "github", "filled")

    assert "audit log write failed" in caplog.text
