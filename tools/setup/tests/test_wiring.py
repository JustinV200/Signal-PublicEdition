"""Wiring writes only finished, chosen tools and keeps the user's own settings."""

import json
import shutil
from pathlib import Path

from signal_setup import progress, registry, wiring

REPO = Path(__file__).resolve().parents[3]


def _finish(data: dict, tool_id: str) -> None:
    """Mark every step of a tool done."""
    for step in registry.by_id(tool_id).steps:
        progress.set_step(data, tool_id, step.id, progress.DONE)


def test_only_finished_tools_are_wired_and_user_entries_survive(tmp_path: Path) -> None:
    shutil.copyfile(REPO / ".mcp.example.json", tmp_path / ".mcp.example.json")
    shutil.copyfile(REPO / ".env.example", tmp_path / ".env.example")
    (tmp_path / ".claude").mkdir()
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
