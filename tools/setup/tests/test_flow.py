"""The terminal setup (`setup --no-ui`) on a checkout whose tools were set up by hand."""

import dataclasses
from pathlib import Path

import pytest

from signal_setup import detect, platforms, progress, registry
from signal_setup.ui import flow
from signal_setup.wiring import ledger


def _brief_set_up_through_setup(root: Path, monkeypatch) -> None:
    """The brief is picked and finished already, so the terminal's wire has entries to add."""
    data = progress.load(root)
    progress.set_step(data, "brief", "install", progress.DONE)
    data["chosen"] = ["brief"]
    progress.save(root, data)


def _job_runner_set_up_by_hand(root: Path, monkeypatch) -> None:
    """The job runner reads as found. Its first step is required and asks first."""
    (root / "tools" / "jobhunt" / ".logs").mkdir(parents=True)


def _mail_asks_its_optional_step_first(root: Path, monkeypatch) -> None:
    """Mail (found) with its optional step moved first, so declining it is the first result."""
    mail = registry.by_id("mail")
    steps = sorted(mail.steps, key=lambda step: not step.optional)
    tools = tuple(
        dataclasses.replace(tool, steps=tuple(steps)) if tool is mail else tool
        for tool in registry.load()
    )
    monkeypatch.setattr(registry, "load", lambda: tools)


@pytest.mark.parametrize(
    ("arrange", "picks", "tool_id", "status", "chosen"),
    [
        # Mail isn't picked: no record is made for it, so it goes on reading as found.
        (_brief_set_up_through_setup, [], "mail", "", ["brief"]),
        # A declined required step on a tool only picked: no record, and it is un-picked.
        (_job_runner_set_up_by_hand, ["jobhunt"], "jobhunt", "", []),
        # A declined optional step on a found tool takes it on: it stays done.
        (_mail_asks_its_optional_step_first, ["mail"], "mail", progress.DONE, ["mail"]),
    ],
)
def test_terminal_setup_leaves_tools_set_up_by_hand_as_they_are(
    tmp_path: Path, monkeypatch, capsys, machine, by_hand, arrange, picks, tool_id, status, chosen
) -> None:
    # Regressions: picking in the terminal marked every other tool skipped, a declined
    # step left a found tool half done or skipped, and the terminal's wire then stripped
    # the entries its owner had made.
    arrange(tmp_path, monkeypatch)
    ids = [tool.id for tool in registry.load()]
    ticks = [str(ids.index(pick) + 1) for pick in picks]
    # The checklist (ticks, then Enter), "n" to the one step that asks, "y" to Add to
    # Claude Code, "n" to the tour. One prompt too many ends the test.
    answers = iter([*ticks, "", *(["n"] if picks else []), "y", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    flow.run_setup(tmp_path)

    out = capsys.readouterr().out
    saved = progress.load(tmp_path)
    tool = registry.by_id(tool_id)
    assert progress.tool_status(saved, tool, platforms.WINDOWS) == status
    assert (tool_id in saved["tools"], saved["chosen"]) == (bool(status), chosen)
    # The checklist reads mail as the lists do, and the closing line agrees with them.
    mail_name = registry.by_id("mail").name
    mail_row = next(line for line in out.splitlines() if f". {mail_name} " in line)
    assert f"done; {detect.FOUND_WORDS}" in mail_row
    if picks:
        # A tool still without a record is found, not finished by setup, and its line says so.
        closing = next(line for line in out.splitlines() if line.startswith(f"{tool.name}: OK"))
        assert (detect.FOUND_WORDS in closing) == (not status) and "is skipped" not in out
    # The terminal's wire changed no entry made by hand.
    assert by_hand.config() == by_hand.with_added(ledger.load(tmp_path))
