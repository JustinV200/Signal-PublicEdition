"""Tests for read-only sign-ins: they keep reading, but a write says to re-run `calendar add`."""

import json
import os
from pathlib import Path

import pytest
from signal_googleauth import protect
from support.calendar_data import EVENTS_PATH, calendar_routes
from support.fakes import SECRET_CLIENT_SECRET, SECRET_REFRESH_TOKEN, FakeResponse, FakeSession

from calendar_tool.auth import LEGACY_SCOPES, open_client
from calendar_tool.auth.token_file import DPAPI_ENTROPY
from calendar_tool.changes import ChangeGate, EventChanges, NewEvent
from calendar_tool.errors import ReauthRequired
from calendar_tool.google_api import CalendarClient, list_selected_calendars

# Google's answer when the access token lacks the write scope.
SCOPE_403 = FakeResponse(
    403, {"error": {"message": "Request had insufficient authentication scopes."}}
)


def client_from_legacy_token(tmp_path: Path) -> CalendarClient:
    """open_client's client for a token file saved by the read-only tool (no "scopes")."""
    client_path, token_path = tmp_path / "google_client.json", tmp_path / "token.bin"
    installed = {
        "client_id": "123.apps.googleusercontent.com",
        "client_secret": SECRET_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    client_path.write_text(json.dumps({"installed": installed}), encoding="utf-8")
    old = json.dumps({"email": "owner@example.com", "refresh_token": SECRET_REFRESH_TOKEN})
    token_path.write_bytes(protect(old.encode("utf-8"), DPAPI_ENTROPY))
    return open_client(client_path, token_path)


@pytest.mark.parametrize("cause", ["legacy token file", "Google's 403"])
def test_a_read_only_sign_in_still_reads_but_a_write_says_re_run_add(
    tmp_path: Path, cause: str
) -> None:
    routes = calendar_routes()
    if cause == "legacy token file":
        if os.name != "nt":
            pytest.skip("DPAPI is Windows-only")
        legacy = client_from_legacy_token(tmp_path)
        can_write = legacy.can_write
        assert can_write is False
        # The refresh asks for what was granted: asking for SCOPES would fail with
        # invalid_scope and stop the idle board's sync.
        assert legacy._session.credentials.scopes == list(LEGACY_SCOPES)
    else:
        can_write, routes[("POST", EVENTS_PATH)] = True, SCOPE_403
    session = FakeSession(routes)
    client = CalendarClient(session, can_write=can_write)

    assert list_selected_calendars(client)  # reads keep working
    with pytest.raises(ReauthRequired, match=r"read-only.*Re-run `calendar add`") as caught:
        EventChanges(client, ChangeGate(True)).create(NewEvent("Dentist", "2026-11-20"))
    assert SECRET_REFRESH_TOKEN not in str(caught.value)
    # The legacy sign-in is refused before anything is sent.
    assert len(session.writes()) == (0 if cause == "legacy token file" else 1)
