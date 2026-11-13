"""Tests for `calendar sync-cache` status: old cache kept on failure, no secret, skips saved."""

import json
from pathlib import Path

import pytest
import requests
from google.auth.exceptions import RefreshError
from support.fakes import SECRET_CLIENT_SECRET, SECRET_REFRESH_TOKEN, FakeSession

from calendar_tool.cli import commands, main
from calendar_tool.cli.sync_status import describe_sync_status
from calendar_tool.google_api import CalendarClient

OLD_CACHE = '{"updated": "2026-10-20T08:00:00-04:00", "events": []}'
LEAKY_REFRESH = RefreshError(
    f"invalid_grant: Bad Request refresh_token={SECRET_REFRESH_TOKEN}",
    {"client_secret": SECRET_CLIENT_SECRET},
)


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (requests.ConnectionError("dns failed"), "Can't reach Google"),
        (LEAKY_REFRESH, "Re-run `calendar add`"),
        (RefreshError(f"weird {SECRET_REFRESH_TOKEN}"), "unknown error"),
    ],
)
def test_a_failed_sync_keeps_the_old_cache_and_prints_no_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: Exception,
    message: str,
) -> None:
    cache = tmp_path / "agenda.json"
    cache.write_text(OLD_CACHE, encoding="utf-8")
    monkeypatch.setattr(commands, "CACHE_PATH", cache)
    status = tmp_path / "sync_status.json"
    monkeypatch.setattr(commands, "SYNC_STATUS_PATH", status)
    session = FakeSession({"users/me/calendarList": failure})
    monkeypatch.setattr(commands, "build_client", lambda: CalendarClient(session))

    exit_code = main(["sync-cache"])

    out, err = capsys.readouterr()
    assert exit_code == 2
    assert message in err and len(err.splitlines()) == 1
    assert cache.read_text(encoding="utf-8") == OLD_CACHE
    # The scheduled run has no stderr, so the failure must land in the status file too.
    saved = json.loads(status.read_text(encoding="utf-8"))
    assert saved["ok"] is False and message in saved["message"]
    for secret in (SECRET_REFRESH_TOKEN, SECRET_CLIENT_SECRET):
        assert secret not in out + err + status.read_text(encoding="utf-8")


def test_a_sync_that_skips_a_calendar_records_it_in_the_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(commands, "CACHE_PATH", tmp_path / "agenda.json")
    status = tmp_path / "sync_status.json"
    monkeypatch.setattr(commands, "SYNC_STATUS_PATH", status)
    calendars = {
        "items": [
            {"id": "a", "summary": "the owner", "selected": True},
            {"id": "b", "summary": "Shared", "selected": True},  # no route: 404
        ]
    }
    session = FakeSession({"users/me/calendarList": calendars, "calendars/a/events": {"items": []}})
    monkeypatch.setattr(commands, "build_client", lambda: CalendarClient(session))

    assert main(["sync-cache"]) == 0

    assert json.loads(status.read_text(encoding="utf-8"))["skipped"] == ["Shared"]
    assert describe_sync_status(status).endswith("(skipped: Shared)")
