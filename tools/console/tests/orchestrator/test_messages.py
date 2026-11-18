"""The chat marker names the owner from SIGNAL_OWNER_NAME in .env, else "the owner"."""

from pathlib import Path

import pytest

from signal_console.orchestrator import chat_request, messages


@pytest.mark.parametrize(
    ("env_text", "name"),
    [
        ('SIGNAL_OWNER_NAME="Sam Example"\n', "Sam Example"),
        ("\ufeffOTHER=1\r\nSIGNAL_OWNER_NAME=Sam\r\n", "Sam"),
        ("SIGNAL_OWNER_NAME=\n", "the owner"),
        ("OTHER=1\n# SIGNAL_OWNER_NAME=Sam\n", "the owner"),
        (None, "the owner"),
    ],
    ids=["quoted", "bom-crlf", "empty", "no key", "no file"],
)
def test_marker_names_the_owner_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, env_text: str | None, name: str
) -> None:
    env = tmp_path / ".env"
    if env_text is not None:
        env.write_bytes(env_text.encode("utf-8"))
    monkeypatch.setattr(messages, "ENV_FILE_PATH", env)

    assert chat_request("hi").orchestrator_text == f"[Signal console] {name}: hi"
