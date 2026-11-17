"""Wiring writes only finished, chosen tools, keeps the user's own settings and backs them up."""

import dataclasses
import json
import shutil
from pathlib import Path

import pytest

from signal_setup import progress, registry, wiring

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _temp_user_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the user settings file at a temp one: no test ever touches the real one."""
    monkeypatch.setattr(wiring, "USER_SETTINGS", tmp_path / "home" / ".claude" / "settings.json")


def _finish(data: dict, tool_id: str) -> None:
    """Mark every step of a tool done."""
    for step in registry.by_id(tool_id).steps:
        progress.set_step(data, tool_id, step.id, progress.DONE)


def _repo(root: Path) -> None:
    """A repo root holding the example files wiring reads."""
    shutil.copyfile(REPO / ".mcp.example.json", root / ".mcp.example.json")
    shutil.copyfile(REPO / ".env.example", root / ".env.example")
    (root / ".claude").mkdir()


def test_only_finished_tools_are_wired_and_user_entries_survive(tmp_path: Path) -> None:
    _repo(tmp_path)
    user = {
        "permissions": {
            "allow": ["Bash(git status)", "mcp__mail__mail_read"],
            "defaultMode": "default",
        },
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "mine"}]}]},
        "model": "opus",
    }
    (tmp_path / ".claude" / "settings.local.json").write_text(json.dumps(user))
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))

    data = progress.load(tmp_path)
    _finish(data, "brief")
    progress.set_step(data, "browser", "install", progress.DONE)  # browser unfinished
    progress.set_skipped(data, "mail")
    tools = registry.load()
    wiring.apply_plan(tmp_path, tools, wiring.build_plan(tools, data, "windows"), "windows")

    mcp = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    settings = json.loads((tmp_path / ".claude" / "settings.local.json").read_text())
    assert set(mcp) == {"other", "brief"}
    # The user's own rule stays; the skipped mail tool's rule is removed.
    assert settings["permissions"]["allow"] == ["Bash(git status)", "mcp__brief"]
    assert settings["permissions"]["defaultMode"] == "default" and settings["model"] == "opus"
    assert settings["enabledMcpjsonServers"] == ["brief"]
    assert settings["hooks"]["Stop"] == user["hooks"]["Stop"]
    brief_hook = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]
    assert brief_hook["args"] == ["-I", "-m", "brief_tool.hooks.prompt"]
    assert (tmp_path / ".env").exists()


def _user_files(root: Path) -> dict[Path, bytes]:
    """The three files wire writes, holding the user's own keys. Returns their bytes.

    The user settings file is the autouse fixture's temp one.
    """
    _repo(root)
    files = {
        root / ".mcp.json": {"mcpServers": {"other": {"command": "x"}}, "mine": True},
        root / ".claude" / "settings.local.json": {"permissions": {"allow": ["Bash(ls)"]}},
        wiring.USER_SETTINGS: {"attribution": {"commit": ""}, "model": "opus"},
    }
    for path, data in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    return {path: path.read_bytes() for path in files}


def _wire(root: Path) -> None:
    """Wire with brief finished and usage's status line wanted."""
    data = progress.load(root)
    _finish(data, "brief")
    tools = registry.load()
    plan = dataclasses.replace(wiring.build_plan(tools, data, "windows"), statusline=True)
    wiring.apply_plan(root, tools, plan, "windows")


def test_wire_backs_up_each_file_before_changing_it(tmp_path: Path) -> None:
    before = _user_files(tmp_path)
    _wire(tmp_path)
    assert all(path.read_bytes() != old for path, old in before.items())
    backups = (tmp_path / ".setup" / "backups").iterdir()
    assert sorted(b.read_bytes() for b in backups) == sorted(before.values())


def test_a_bad_user_settings_file_stops_wire_before_any_write(tmp_path: Path) -> None:
    before = _user_files(tmp_path)
    wiring.USER_SETTINGS.write_text("{not json")
    with pytest.raises(wiring.WiringError):
        _wire(tmp_path)
    for path in (tmp_path / ".mcp.json", tmp_path / ".claude" / "settings.local.json"):
        assert path.read_bytes() == before[path]


def test_a_second_wire_changes_nothing_and_keeps_other_keys(tmp_path: Path) -> None:
    files = _user_files(tmp_path)
    _wire(tmp_path)
    first = {path: path.read_bytes() for path in files}
    _wire(tmp_path)
    assert {path: path.read_bytes() for path in files} == first
    mcp, local, user = (json.loads(raw) for raw in first.values())
    assert mcp["mine"] and set(mcp["mcpServers"]) == {"other", "brief"}
    assert local["permissions"]["allow"] == ["Bash(ls)", "mcp__brief"]
    assert user["attribution"] == {"commit": ""} and user["model"] == "opus"
    assert "usage.statusline" in user["statusLine"]["command"]


def test_browser_auto_approve_follows_its_steps() -> None:
    data = progress.load(Path("nowhere"))
    _finish(data, "browser")
    plan = wiring.build_plan(registry.load(), data, "windows")
    assert plan.mcp_servers == ("browser", "browser-docker")
    assert plan.allow == ("mcp__browser", "mcp__browser-docker")
    progress.set_step(data, "browser", "docker", progress.SKIPPED)
    progress.set_step(data, "browser", "auto-approve", progress.SKIPPED)
    plan = wiring.build_plan(registry.load(), data, "windows")
    assert plan.mcp_servers == ("browser",) and plan.allow == ()
