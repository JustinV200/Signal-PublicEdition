"""Tests for load_client_config: bad client files are refused without echoing the secret."""

import json
from pathlib import Path

import pytest

from signal_googleauth import ClientFileError, load_client_config

SECRET = "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k"
GOOD = {
    "client_id": "123.apps.googleusercontent.com",
    "client_secret": SECRET,
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "project_id": "signal-512122",
}


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({"web": GOOD}, "Desktop app"),
        ({"installed": {**GOOD, "token_uri": "https://evil.example/token"}}, "token_uri"),
        ({"installed": {k: v for k, v in GOOD.items() if k != "client_id"}}, "client_id"),
    ],
)
def test_bad_client_files_are_refused_without_the_secret(
    tmp_path: Path, payload: dict, match: str
) -> None:
    path = tmp_path / "google_client.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ClientFileError, match=match) as caught:
        load_client_config(path)

    assert SECRET not in str(caught.value)


def test_a_desktop_client_loads_and_hides_its_secret_from_repr(tmp_path: Path) -> None:
    path = tmp_path / "google_client.json"
    path.write_text(json.dumps({"installed": GOOD}), encoding="utf-8")

    client = load_client_config(path)

    assert client.project_id == "signal-512122"
    assert SECRET not in repr(client)
