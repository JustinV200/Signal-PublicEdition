"""Tool health for the console's System Tools list, and the setup window's terminal fallback."""

import dataclasses
import subprocess
from pathlib import Path

import pytest

from signal_setup import health, progress, registry, verify


@pytest.mark.parametrize(
    ("setup_status", "check", "state"),
    [
        ("", None, health.NOT_SET_UP),
        (progress.SKIPPED, None, health.NOT_SET_UP),
        (progress.STARTED, None, health.NOT_SET_UP),
        (progress.FAILED, None, health.NOT_SET_UP),
        (progress.DONE, verify.CheckResult(True, "installed"), health.ACTIVE),
        (progress.DONE, verify.CheckResult(False, "timed out after 8 s"), health.DOWN),
        (progress.DONE, None, health.DOWN),
    ],
)
def test_classify(setup_status, check, state) -> None:
    assert health.classify(setup_status, check)[0] == state


def test_health_rows_only_check_finished_tools(tmp_path: Path, monkeypatch) -> None:
    data = progress.load(tmp_path)
    progress.set_step(data, "brief", "install", progress.DONE)
    progress.set_skipped(data, "usage")
    progress.save(tmp_path, data)
    checked = []
    monkeypatch.setattr(
        health.verify,
        "check",
        lambda root, tool, data, t: checked.append(tool.id) or verify.CheckResult(False, "x"),
    )

    rows = {r["id"]: r["state"] for r in health.health_rows(tmp_path)}

    assert checked == ["brief"]
    assert rows["brief"] == health.DOWN
    assert rows["usage"] == rows["mail"] == health.NOT_SET_UP


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
