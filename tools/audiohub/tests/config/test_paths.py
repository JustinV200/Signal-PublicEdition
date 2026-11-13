"""Tests for audiohub.config.paths: the derived tool and repo locations."""

from audiohub.config import CACHE_DIR, DEFAULT_CONFIG_PATH, MODELS_DIR, REPO_ROOT, TOOL_ROOT


def test_tool_root_is_the_uv_project():
    assert (TOOL_ROOT / "pyproject.toml").is_file()
    assert TOOL_ROOT.name == "audiohub"


def test_repo_root_holds_agents_md():
    assert (REPO_ROOT / "AGENTS.md").is_file()


def test_local_files_live_in_the_tool_root():
    assert MODELS_DIR.parent == TOOL_ROOT
    assert CACHE_DIR == TOOL_ROOT / ".cache"
    assert DEFAULT_CONFIG_PATH == TOOL_ROOT / "audiohub.toml"
