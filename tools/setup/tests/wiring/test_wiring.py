"""Wiring writes only finished, chosen tools, keeps the user's own settings and backs them
up; wired_tools only reads which are in. What wire may take out again: test_ledger.py."""

import dataclasses
import json
import shutil
from pathlib import Path

import pytest

from signal_setup import progress, registry, wiring

REPO = Path(__file__).resolve().parents[4]


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
    wiring.apply_plan(tmp_path, wiring.build_plan(registry.load(), data, "windows"), "windows")

    mcp = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    settings = json.loads((tmp_path / ".claude" / "settings.local.json").read_text())
    assert set(mcp) == {"other", "brief"}
    # The user's own rules stay, the one for the skipped mail tool too: setup didn't add it.
    assert settings["permissions"]["allow"] == [*user["permissions"]["allow"], "mcp__brief"]
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
    plan = wiring.build_plan(registry.load(), data, "windows")
    wiring.apply_plan(root, dataclasses.replace(plan, statusline=True), "windows")


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
    def snapshot() -> dict[Path, bytes]:
        return {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    files = _user_files(tmp_path)
    _wire(tmp_path)
    # Entries made after setup's, as Claude Code adds each approval to the allow list.
    local_file = tmp_path / ".claude" / "settings.local.json"
    local = json.loads(local_file.read_text())
    local["permissions"]["allow"].append("Bash(git status)")
    local["enabledMcpjsonServers"].append("other")
    own_hook = {"type": "command", "command": "mine"}
    local["hooks"]["UserPromptSubmit"][0]["hooks"].append(own_hook)
    local["hooks"]["UserPromptSubmit"].append({"hooks": [own_hook]})
    local_file.write_text(json.dumps(local))
    first = snapshot()

    _wire(tmp_path)

    # Regression: setup's entries were taken out and added back last, so this wire
    # reordered the lists, rewrote the file and overwrote its backup.
    assert snapshot() == first  # byte for byte, the backups too
    mcp, local, user = (json.loads(first[path]) for path in files)
    assert mcp["mine"] and set(mcp["mcpServers"]) == {"other", "brief"}
    assert local["permissions"]["allow"] == ["Bash(ls)", "mcp__brief", "Bash(git status)"]
    assert user["attribution"] == {"commit": ""} and user["model"] == "opus"
    assert "usage.statusline" in user["statusLine"]["command"]

    # Setup's entries the owner deletes come back while their tool is still wanted.
    local["permissions"]["allow"].remove("mcp__brief")
    brief_hook = local["hooks"]["UserPromptSubmit"][0]["hooks"].pop(0)
    local_file.write_text(json.dumps(local))
    _wire(tmp_path)
    local = json.loads(local_file.read_text())
    assert local["permissions"]["allow"] == ["Bash(ls)", "Bash(git status)", "mcp__brief"]
    assert local["hooks"]["UserPromptSubmit"][-1] == {"hooks": [brief_hook]}


def test_wired_only_reads_and_needs_every_server_and_hook(tmp_path: Path) -> None:
    def snapshot() -> dict[Path, bytes]:
        return {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    def wired() -> set[str]:
        before = snapshot()
        found = wiring.wired_tools(tmp_path, registry.load(), data, "windows")
        assert snapshot() == before  # read only: no file written, made or removed
        return found

    _repo(tmp_path)
    data = progress.load(tmp_path)
    _finish(data, "brief")
    assert wired() == set()  # finished, but wire never ran
    wiring.apply_plan(tmp_path, wiring.build_plan(registry.load(), data, "windows"), "windows")
    assert wired() == {"brief"}
    local = tmp_path / ".claude" / "settings.local.json"
    hooks = json.loads(local.read_text()).pop("hooks")
    local.write_text(json.dumps({"permissions": {}}))
    assert wired() == set()  # its server is there, its hook isn't
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps({"hooks": hooks}))
    assert wired() == {"brief"}  # a hook in the checked-in project settings counts
    (tmp_path / ".mcp.json").write_text("{not json")
    assert wired() == set()


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
    # The window splits at the gap: the exact entries come after it.
    lines = wiring.summary_lines(plan)
    assert "  nothing" in lines[lines.index("") :]


@pytest.mark.parametrize(
    ("tool_id", "granting_step"),
    [("browser", "auto-approve"), ("mail-digest", "schedule"), ("jobhunt", "schedule")],
)
def test_consent_words_show_only_once_the_granting_step_is_done(tool_id, granting_step) -> None:
    tool = registry.by_id(tool_id)
    data = progress.load(Path("nowhere"))
    _finish(data, tool_id)
    assert wiring.build_plan(registry.load(), data, "windows").consent == (
        f"{tool.name}: {tool.consent}",
    )
    progress.set_step(data, tool_id, granting_step, progress.SKIPPED)
    (line,) = wiring.build_plan(registry.load(), data, "windows").consent
    assert line.startswith(f"{tool.name}: ") and tool.consent not in line


def test_every_tool_that_grants_something_has_consent_words() -> None:
    def adds(tool: registry.Tool) -> bool:
        granting = any(s.permissions or s.unattended_claude for s in tool.steps)
        return bool(tool.permissions or tool.hooks or granting)

    assert [t.id for t in registry.load() if adds(t) and not t.consent] == []
    # One line each: the page and the terminal show it as a single line.
    assert [t.id for t in registry.load() if "\n" in t.consent] == []
