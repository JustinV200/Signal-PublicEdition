"""Public API wiring: list_credentials reads the default store and exposes hints only."""

import pytest

from vault import list_credentials
from vault.paths import DATA_DIR_NAME, STORE_FILE_NAME


@pytest.mark.asyncio
async def test_list_credentials_shows_a_hint_not_the_username(tmp_path, monkeypatch, fill_env):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    (tmp_path / DATA_DIR_NAME).mkdir()
    fill_env.store_path.replace(tmp_path / DATA_DIR_NAME / STORE_FILE_NAME)

    (info,) = list_credentials()

    assert info.id == fill_env.credential_id
    assert info.username_hint == "o***@example.test"
    assert fill_env.username not in repr(info)
