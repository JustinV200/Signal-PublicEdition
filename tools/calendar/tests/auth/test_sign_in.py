"""Tests for sign_in: only the two read-only scopes; saves the token only for the right account."""

import json
import os
from pathlib import Path

import pytest
from google.oauth2.credentials import Credentials
from support.fakes import SECRET_CLIENT_SECRET, SECRET_REFRESH_TOKEN

from calendar_tool.auth import SCOPES, load_sign_in, sign_in
from calendar_tool.errors import CalendarError

pytestmark = pytest.mark.skipif(os.name != "nt", reason="DPAPI is Windows-only")

READ_ONLY_SCOPES = {
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
}


def write_client(path: Path) -> None:
    installed = {
        "client_id": "123.apps.googleusercontent.com",
        "client_secret": SECRET_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    path.write_text(json.dumps({"installed": installed}), encoding="utf-8")


@pytest.mark.parametrize(
    ("signed_in_as", "is_saved"),
    [("owner@example.com", True), ("someone-else@example.com", False)],
)
def test_sign_in_asks_only_read_only_scopes_and_checks_the_account(
    tmp_path: Path, signed_in_as: str, is_saved: bool
) -> None:
    client_path, token_path = tmp_path / "google_client.json", tmp_path / "token.bin"
    write_client(client_path)
    asked: list[tuple[str, ...]] = []

    def fake_flow(path: Path, scopes: tuple[str, ...], hint: str | None, page: str) -> Credentials:
        asked.append(tuple(scopes))
        return Credentials(token=None, refresh_token=SECRET_REFRESH_TOKEN)

    def run() -> str:
        paths = (client_path, token_path)
        return sign_in(paths, "owner@example.com", fake_flow, lambda _c: signed_in_as)

    if is_saved:
        run()
        assert load_sign_in(token_path).refresh_token == SECRET_REFRESH_TOKEN
        assert SECRET_REFRESH_TOKEN.encode() not in token_path.read_bytes()
    else:
        with pytest.raises(CalendarError, match="nothing was saved"):
            run()
        assert not token_path.exists()
    assert set(SCOPES) == READ_ONLY_SCOPES and len(SCOPES) == 2
    assert asked == [tuple(SCOPES)]
