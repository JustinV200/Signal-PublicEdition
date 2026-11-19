"""Tool health for the console's System Tools list (tools found already set up by hand
included), and what a verify check's output reads as."""

import dataclasses
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from signal_setup import detect, health, platforms, progress, registry, verify
from signal_setup.cli import agent, main

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("setup_status", "check", "state"),
    [
        # The other states are rows of test_health_rows_find_a_tool_set_up_by_hand.
        (progress.STARTED, None, health.NOT_SET_UP),
        (progress.DONE, None, health.DOWN),
    ],
)
def test_classify(setup_status, check, state) -> None:
    assert health.classify(setup_status, check)[0] == state


BRIEF_HOOK = {"type": "command", "args": ["-I", "-m", "brief_tool.hooks.prompt"]}


def _set_up_brief_by_hand(root: Path, has_evidence: bool = True, is_wired: bool = True) -> None:
    """Make `root` look as if brief was set up without setup: its venv, server and hook."""
    if has_evidence:
        (root / "tools" / "brief" / ".venv").mkdir(parents=True)
    if is_wired:
        (root / ".claude").mkdir()
        settings = {"hooks": {"UserPromptSubmit": [{"hooks": [BRIEF_HOOK]}]}}
        (root / ".claude" / "settings.local.json").write_text(json.dumps(settings))
        (root / ".mcp.json").write_text(json.dumps({"mcpServers": {"brief": {}}}))


def _fake_checks(monkeypatch, passes: bool) -> list[str]:
    """Replace every verify check with one that passes or fails; returns the ids it's asked for."""
    checked: list[str] = []
    result = verify.CheckResult(passes, "installed" if passes else "check failed (exit 1)")
    monkeypatch.setattr(verify, "check", lambda root, tool, *_: checked.append(tool.id) or result)
    return checked


FOUND = f"installed · {detect.FOUND_WORDS}"


@pytest.mark.parametrize(
    ("record", "has_evidence", "is_wired", "passes", "state", "words", "is_checked"),
    [
        # No record, but it works and is in Claude Code: found, and the row says how it knows.
        (None, True, True, True, health.ACTIVE, FOUND, True),
        # Picked only (what Re-run setup records before any step runs): still found.
        ("picked", True, True, True, health.ACTIVE, FOUND, True),
        # A failing check is never Down without a record that says finished.
        (None, True, True, False, health.NOT_SET_UP, "", True),
        # A check that would pass proves nothing without local evidence (a fresh clone
        # that ships the config), or while Claude Code's config lacks the tool.
        (None, False, True, True, health.NOT_SET_UP, "", False),
        (None, True, False, True, health.NOT_SET_UP, "", False),
        # The record wins: a skip, a failed step, and a finished tool whose check fails.
        ("skipped", True, True, True, health.NOT_SET_UP, "skipped", False),
        (progress.FAILED, True, True, True, health.NOT_SET_UP, "a setup step failed", False),
        (progress.DONE, False, True, False, health.DOWN, "check failed (exit 1)", True),
    ],
)
def test_health_rows_find_a_tool_set_up_by_hand(
    tmp_path: Path, monkeypatch, record, has_evidence, is_wired, passes, state, words, is_checked
) -> None:
    _set_up_brief_by_hand(tmp_path, has_evidence, is_wired)
    data = progress.load(tmp_path)
    if record == "skipped":
        progress.set_skipped(data, "brief")
    elif record == "picked":
        progress.set_skipped(data, "brief", False)
    elif record:
        progress.set_step(data, "brief", "install", record)
    if record:
        progress.save(tmp_path, data)
    checked = _fake_checks(monkeypatch, passes)

    rows = {row["id"]: row for row in health.health_rows(tmp_path)}

    assert (rows["brief"]["state"], rows["brief"]["words"]) == (state, words)
    assert rows["brief"]["detected"] == (words == FOUND)
    # Only brief is ever looked at: nothing else has a record or evidence.
    assert checked == (["brief"] if is_checked else [])
    assert rows["usage"]["state"] == rows["mail"]["state"] == health.NOT_SET_UP


def _lists(root: Path, monkeypatch, capsys) -> tuple[dict, dict, str]:
    """Brief's row in `status --json` and in `list`, and terminal `status`'s lines."""
    health_row = next(row for row in health.health_rows(root) if row["id"] == "brief")
    capsys.readouterr()
    agent.list_tools(root)
    listed = next(tool for tool in json.loads(capsys.readouterr().out) if tool["id"] == "brief")
    monkeypatch.setattr(main, "REPO_ROOT", root)
    assert main.main(["status"]) == 0
    return health_row, listed, capsys.readouterr().out


def test_a_fresh_clone_lists_every_tool_as_not_set_up(tmp_path: Path, monkeypatch, capsys) -> None:
    # Every check would pass (a fresh clone fools some: they only read checked-in files),
    # and none is even run: no tool has its evidence, so nothing reads set up.
    checked = _fake_checks(monkeypatch, passes=True)

    states = {row["state"] for row in health.health_rows(tmp_path)}
    _, listed, lines = _lists(tmp_path, monkeypatch, capsys)

    assert states == {health.NOT_SET_UP}
    assert listed["status"] == "not set up" and "done" not in lines
    assert checked == []
    assert list(tmp_path.iterdir()) == []  # reading the lists writes nothing


def test_a_found_tool_reads_the_same_in_every_list(tmp_path: Path, monkeypatch, capsys) -> None:
    _set_up_brief_by_hand(tmp_path)
    _fake_checks(monkeypatch, passes=True)

    health_row, listed, lines = _lists(tmp_path, monkeypatch, capsys)

    assert (health_row["state"], health_row["wired"]) == (health.ACTIVE, True)
    assert (listed["status"], listed["wired"], listed["detected"]) == (progress.DONE, True, True)
    # Setup ran none of its steps, and says so: the record stays what was saved (nothing).
    assert [step["status"] for step in listed["steps"]] == [""]
    brief_line = next(line for line in lines.splitlines() if line.startswith("brief"))
    assert progress.DONE in brief_line and detect.FOUND_WORDS in brief_line
    assert not (tmp_path / ".setup").exists()


def test_a_found_tool_runs_on_defaults_without_its_optional_config(
    tmp_path: Path, monkeypatch
) -> None:
    # Only the check's command is faked: the real verify.check scans for placeholders, and
    # would call the config file that was never made (sleepmode.toml) missing.
    monkeypatch.setattr(platforms, "current", lambda: platforms.WINDOWS)  # sleepmode's OS
    monkeypatch.setattr(verify.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        verify.subprocess, "run", lambda argv, **_: subprocess.CompletedProcess(argv, 0, "", "")
    )
    (tmp_path / "tools" / "sleepmode" / ".venv").mkdir(parents=True)
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"sleepmode": {}}}))

    def row() -> dict:
        return next(row for row in health.health_rows(tmp_path) if row["id"] == "sleepmode")

    assert (row()["state"], row()["detected"]) == (health.ACTIVE, True)
    # Taken on with its first step result: the record setup saves carries the skip too.
    assert agent.mark(tmp_path, "sleepmode", "openrgb", progress.SKIPPED) == 0
    assert (row()["state"], row()["detected"]) == (health.ACTIVE, False)


def test_no_evidence_path_is_checked_in() -> None:
    # A path in the repo exists on a fresh clone, so it could never show a tool was set up.
    paths = sorted({path for tool in registry.load() for path in tool.evidence})
    git = shutil.which("git")
    listed = git and subprocess.run(
        [git, "ls-files", "--", *paths], cwd=REPO, capture_output=True, text=True
    )
    if not listed or listed.returncode != 0:
        pytest.skip("not a git checkout")
    assert listed.stdout == ""


# Nothing to run, so nothing to check: Signal's own rules (AGENTS.md) and copytone's samples.
NO_PROGRAM = {"agents", "copytone"}
# A check that only proves the program starts: help text, or `python -c "import x"`.
STARTS_ONLY_ARGS = {"-h", "--help", "help", "-c"}


@pytest.mark.parametrize(
    "tool", [t for t in registry.load() if t.id not in NO_PROGRAM], ids=lambda t: t.id
)
def test_every_tool_has_a_real_check_and_a_fix(tool: registry.Tool) -> None:
    assert tool.verify
    assert not STARTS_ONLY_ARGS & set(tool.verify)
    assert not any(arg.startswith("import ") for arg in tool.verify)
    assert tool.fix


SUMMARY_LINE = '{"words": "Turn hook: missing", "fix": "Add it.", "command": "setup console"}'
REGISTRY_FIX = "Set brief up again."
STDERR_LINE = "ModuleNotFoundError: No module named 'brief'"


@pytest.mark.parametrize(
    ("returncode", "stdout", "expected"),
    [
        # The last stdout line is the check's summary: its words, fix and command win.
        (
            1,
            f"FAIL  Turn hook\n{SUMMARY_LINE}\n",
            verify.CheckResult(False, "Turn hook: missing", "Add it.", "setup console"),
        ),
        # A plain last line (here help text) is never the words: a pass is "installed".
        (0, "usage: brief [-h] {away}\n", verify.CheckResult(True, verify.PASS_WORDS)),
        # A failure without a summary takes the registry's fix and keeps stderr's last line.
        (
            2,
            "Traceback ...\n",
            verify.CheckResult(False, "check failed (exit 2)", REGISTRY_FIX, output=STDERR_LINE),
        ),
        # Fields are stripped; a blank fix is none.
        (0, '{"words": "  running  ", "fix": " "}\n', verify.CheckResult(True, "running")),
        # Not a summary, so the words are plain: a line break (a copied command would run
        # twice), any other control character, blank words, or a field past the cap.
        *(
            (0, line, verify.CheckResult(True, verify.PASS_WORDS))
            for line in (
                '{"words": "ok", "command": "setup x\\nrm -rf ."}\n',
                '{"words": "ok\\u001b[2J", "fix": null}\n',
                '{"words": "ok", "fix": "tab\\there"}\n',
                '{"words": "ok\\u009b2J"}\n',
                '{"words": "   "}\n',
                '{"words": "' + "x" * (verify.MAX_SUMMARY_CHARS + 1) + '"}\n',
            )
        ),
    ],
)
def test_verify_check_reads_the_summary_line(
    tmp_path: Path, monkeypatch, returncode, stdout, expected
) -> None:
    # Regression: setup's VIRTUAL_ENV leaked into a nested `uv run`, whose stderr warning
    # became the Tools list's words.
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / ".venv"))
    monkeypatch.setattr(verify.shutil, "which", lambda name: rf"C:\bin\{name}.exe")
    seen = {}

    def fake_run(argv, **kwargs):
        seen.update(argv=argv, **kwargs)
        return subprocess.CompletedProcess(argv, returncode, stdout, f"\n{STDERR_LINE}\n\n")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)
    brief = dataclasses.replace(registry.by_id("brief"), fix=REGISTRY_FIX)

    assert verify.check(tmp_path, brief, progress.load(tmp_path)) == expected
    assert seen["argv"][0] == r"C:\bin\uv.exe"
    assert "VIRTUAL_ENV" not in seen["env"]
    # Regression: locale decoding (cp1252) raised on a character it can't decode.
    assert (seen["env"]["PYTHONIOENCODING"], seen["errors"]) == ("utf-8", "replace")
