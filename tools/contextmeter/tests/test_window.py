"""Tests for which context window applies: env var, then contextmeter.toml, then the table."""

import pytest

from contextmeter.config import configured_window
from contextmeter.window import context_window


@pytest.mark.parametrize(
    ("env", "config_text", "model", "used", "expected"),
    [
        (None, None, "claude-opus-5-5", 10, 1_000_000),  # table row, no config file
        (None, None, "claude-haiku-5-5", 300_000, 1_000_000),  # past 200k: must be 1M
        (None, "window_tokens = 0\n", "claude-haiku-5-5", 10, 200_000),  # 0 keeps the table
        (None, "window_tokens = 200000\n", "claude-opus-5-5", 10, 200_000),  # config wins
        ("400000", "window_tokens = 200000\n", "claude-opus-5-5", 10, 400_000),  # env wins
    ],
)
def test_window_precedence(monkeypatch, tmp_path, env, config_text, model, used, expected):
    if env is None:
        monkeypatch.delenv("CONTEXTMETER_WINDOW_TOKENS", raising=False)
    else:
        monkeypatch.setenv("CONTEXTMETER_WINDOW_TOKENS", env)
    config_file = tmp_path / "contextmeter.toml"
    if config_text is not None:
        config_file.write_text(config_text, encoding="utf-8")
    assert context_window(model, used, configured_window(config_file)) == expected
