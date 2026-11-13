"""Tests for sharing the whiteboard's projector name match."""

from pathlib import Path

from sleepmode.config import DEFAULT_PROJECTOR_MATCH, projector_match


def test_uses_the_whiteboard_name_match_else_the_default(tmp_path: Path) -> None:
    config = tmp_path / "whiteboard.toml"
    assert projector_match(config) == DEFAULT_PROJECTOR_MATCH
    config.write_text('[display]\nname_match = "PROJ-1"\n', encoding="utf-8")
    assert projector_match(config) == "PROJ-1"
    config.write_text("[display]\nname_match = 3\n", encoding="utf-8")
    assert projector_match(config) == DEFAULT_PROJECTOR_MATCH
    config.write_text("not toml [", encoding="utf-8")
    assert projector_match(config) == DEFAULT_PROJECTOR_MATCH
