"""Tests for load_client_config: a Web client is refused without echoing the secret."""

import json
from pathlib import Path

import pytest
from support.fakes import SECRET_CLIENT_SECRET

from mail_tool.auth import load_client_config
from mail_tool.errors import SetupError


def test_client_file_errors_never_echo_the_secret(tmp_path: Path) -> None:
    path = tmp_path / "google_client.json"
    web = {"client_id": "x", "client_secret": SECRET_CLIENT_SECRET}
    path.write_text(json.dumps({"web": web}), encoding="utf-8")

    with pytest.raises(SetupError, match="Desktop app") as caught:
        load_client_config(path)

    assert SECRET_CLIENT_SECRET not in str(caught.value)
