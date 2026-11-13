"""Tests for AccountSignIn (`mail add`): the signed-in address must match --email."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from support.fakes import SECRET_CLIENT_SECRET, SECRET_REFRESH_TOKEN, FakeStore

from mail_tool.errors import AccountError
from mail_tool.service import AccountSignIn


class SavingStore(FakeStore):
    def save(self, record) -> None:
        self.records[record.alias] = record


@pytest.fixture
def client_path(tmp_path: Path) -> Path:
    path = tmp_path / "google_client.json"
    installed = {
        "client_id": "123.apps.googleusercontent.com",
        "client_secret": SECRET_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "project_id": "signal-mail",
    }
    path.write_text(json.dumps({"installed": installed}), encoding="utf-8")
    return path


def _sign_in(
    store: SavingStore, client_path: Path, signed_in_as: str
) -> tuple[AccountSignIn, list[str | None]]:
    """An AccountSignIn whose browser flow 'signs in' as signed_in_as; also the login hints."""
    hints: list[str | None] = []

    def run_flow(_path: Path, login_hint: str | None) -> SimpleNamespace:
        hints.append(login_hint)
        return SimpleNamespace(refresh_token=SECRET_REFRESH_TOKEN)

    return AccountSignIn(store, client_path, run_flow, lambda _c, _a: signed_in_as), hints


def test_a_different_signed_in_account_saves_nothing(client_path: Path) -> None:
    store = SavingStore()
    sign_in, hints = _sign_in(store, client_path, signed_in_as="someone.else@example.com")

    with pytest.raises(AccountError, match="not owner@example.com") as caught:
        sign_in.add("personal", "owner@example.com")

    assert store.records == {}
    assert hints == ["owner@example.com"]
    assert SECRET_REFRESH_TOKEN not in str(caught.value)


def test_a_matching_account_is_saved_under_the_normalized_alias(client_path: Path) -> None:
    store = SavingStore()
    sign_in, _hints = _sign_in(store, client_path, signed_in_as="owner@school.example.edu")

    record = sign_in.add("School", "owner@school.example.edu")

    assert store.records == {"school": record}
    assert record.email == "owner@school.example.edu" and SECRET_REFRESH_TOKEN not in repr(record)
