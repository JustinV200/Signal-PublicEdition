"""Shared fixtures for the setup tool's tests: the real repo files some tests read, a fake
machine, and a checkout whose Claude Code config was written by hand.

A few registry files exist only in the public edition (other tools' example configs, the
root README, AGENTS.md's setting marker). Outside the public edition, a test that reads one
skips when it's missing instead of failing. In the public edition nothing skips: a missing
file or marker there is real drift, so the test fails as it always did.
"""

import copy
import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from signal_setup import platforms, verify, wiring
from signal_setup.wiring import ledger

REPO = Path(__file__).resolve().parents[3]
# Only the public edition ships it; there a missing file or marker is real drift, so let
# the test fail.
IS_PUBLIC_EDITION = (REPO / "COMMERCIAL.md").is_file()
# Files that only count as present when they hold this marker (the private edition's
# AGENTS.md has the rule's prose but not setup's marker).
REQUIRED_MARKERS = {"AGENTS.md": "<!-- setting:context-handoff-percent -->"}


@pytest.fixture
def repo_file() -> Callable[[str], Path]:
    """A function giving the real repo file at a relative path, or skipping the test.

    Outside the public edition the function skips when the file is missing, or lacks its
    REQUIRED_MARKERS entry. In the public edition it never skips.
    """

    def find(relative: str) -> Path:
        path = REPO / relative
        if IS_PUBLIC_EDITION:
            return path
        if not path.is_file():
            pytest.skip(f"public-edition file not in this checkout: {relative}")
        marker = REQUIRED_MARKERS.get(relative)
        if marker and marker not in path.read_text("utf-8"):
            pytest.skip(f"public-edition marker not in this checkout: {marker} in {relative}")
        return path

    return find


@pytest.fixture
def machine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """A fake machine, for tests that drive setup's real write paths on tmp_path.

    It is Windows (the tools' OS) with every program installed. A step's command starts
    nothing and exits `returncode`, every verify check passes or fails by `checks_pass`,
    and the user's own settings file is a temp one. The test changes either through the
    object this gives.
    """
    state = SimpleNamespace(returncode=0, checks_pass=True)
    monkeypatch.setattr(wiring, "USER_SETTINGS", tmp_path / "home" / ".claude" / "settings.json")
    monkeypatch.setattr(platforms, "current", lambda: platforms.WINDOWS)
    monkeypatch.setattr(shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        subprocess, "run", lambda argv, cwd: SimpleNamespace(returncode=state.returncode)
    )
    monkeypatch.setattr(
        verify, "check", lambda *_: verify.CheckResult(state.checks_pass, "installed")
    )
    return state


def _mine(*args: str) -> dict[str, Any]:
    """A hook the owner wrote by hand: not the command setup would write."""
    return {"type": "command", "command": "mine", "args": list(args)}


TURN_HOOK = _mine("-m", "signal_console.hooks.turn")
USAGE_HOOK = _mine("-I", "-m", "usage.hook")
# Evidence that these were installed here. Mail and the browser then read as found; the
# console doesn't, since its session hook is missing.
BY_HAND_VENVS = ("mail", "browser", "console")
BY_HAND_MCP = {
    # browser-docker is a server only an optional step grants; `other` is no tool of setup's.
    "mcpServers": {n: {"command": "mine"} for n in ("mail", "browser", "browser-docker", "other")},
    "mine": True,
}
BY_HAND_SETTINGS = {
    "permissions": {
        # The browser rules are ones only an optional step grants.
        "allow": ["Bash(ls)", "mcp__mail__mail_read", "mcp__browser", "mcp__browser-docker"],
        "defaultMode": "default",
    },
    "enabledMcpjsonServers": ["other"],
    "hooks": {
        "Stop": [{"hooks": [TURN_HOOK]}],
        "SubagentStart": [{"hooks": [USAGE_HOOK, TURN_HOOK]}],  # two tools' hooks, one group
    },
    "model": "opus",
}
# The checked-in project settings hold usage's other hook.
BY_HAND_PROJECT_SETTINGS = {"hooks": {"SubagentStop": [{"hooks": [USAGE_HOOK]}]}}


class ByHand:
    """A repo root whose Claude Code config someone wrote by hand, and what it held."""

    mcp = BY_HAND_MCP
    settings = BY_HAND_SETTINGS

    def __init__(self, root: Path) -> None:
        """Write the example files wiring reads, the venvs and the three config files."""
        for name in (".mcp.example.json", ".env.example"):
            shutil.copyfile(REPO / name, root / name)
        for tool_id in BY_HAND_VENVS:
            (root / "tools" / tool_id / ".venv").mkdir(parents=True)
        (root / ".claude").mkdir()
        self.files = (root / ".mcp.json", root / ".claude" / "settings.local.json")
        for path, content in zip(self.files, (self.mcp, self.settings), strict=True):
            path.write_text(json.dumps(content))
        self.project_settings = root / ".claude" / "settings.json"
        self.project_settings.write_text(json.dumps(BY_HAND_PROJECT_SETTINGS))
        self.project_bytes = self.project_settings.read_bytes()

    def config(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """.mcp.json and .claude/settings.local.json as they are now."""
        mcp, settings = (json.loads(path.read_text("utf-8")) for path in self.files)
        return mcp, settings

    def with_added(self, added: ledger.Ledger) -> tuple[dict[str, Any], dict[str, Any]]:
        """Both files as written by hand, plus exactly what the ledger says setup added.

        The config equals this when every hand-made entry is still there, unchanged and
        in place, and setup added nothing its ledger doesn't list.
        """
        mcp, settings = copy.deepcopy((self.mcp, self.settings))
        mcp["mcpServers"].update(added.servers)
        settings["permissions"]["allow"] += added.allow
        settings["enabledMcpjsonServers"] += added.enabled
        for record in added.hooks:
            settings["hooks"].setdefault(record["event"], []).append({"hooks": [record["hook"]]})
        return mcp, settings


@pytest.fixture
def by_hand(tmp_path: Path) -> ByHand:
    """tmp_path as a checkout set up by hand: see ByHand."""
    return ByHand(tmp_path)
