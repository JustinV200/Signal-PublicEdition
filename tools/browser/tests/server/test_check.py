"""`browser-tool --check`: passes only a config the server could start with."""

from pathlib import Path

import pytest

from browser_tool.server.check import EXIT_CONFIG_ERROR, EXIT_OK, check_summary


@pytest.mark.parametrize(
    ("toml", "code", "words_start"),
    [
        ('[policy]\nallow = ["github.com", "*.example.org"]\n', EXIT_OK, "config OK, 2 sites"),
        ("[policy]\nallow = []\n", EXIT_OK, "config OK, but no site"),
        ("[nope]\nx = 1\n", EXIT_CONFIG_ERROR, "config problem:"),
        # Regression: loaded fine, but the server refuses the pattern at start.
        ('[policy]\nallow = ["https://github.com/x"]\n', EXIT_CONFIG_ERROR, "config problem:"),
        ('[duo]\ncode_relay_sites = ["a b"]\n', EXIT_CONFIG_ERROR, "config problem: [duo]"),
    ],
)
def test_check_summary(tmp_path: Path, toml: str, code: int, words_start: str) -> None:
    config = tmp_path / "browser.toml"
    config.write_text(toml, encoding="utf-8")

    exit_code, summary = check_summary(config)

    assert (exit_code, summary["words"][: len(words_start)]) == (code, words_start)
