"""Wire's ledger: wire takes out only what it added itself, whatever setup's record says."""

import copy
import json
from pathlib import Path

import pytest

from signal_setup import platforms, progress, registry, wiring
from signal_setup.cli import agent, ui_launch
from signal_setup.cli.auto import run_automatic
from signal_setup.ui import flow
from signal_setup.wiring import ledger

# A hook the owner later puts in the very group setup made for the brief's.
OWN_HOOK = {"type": "command", "command": "mine-too"}


def _nothing(root: Path, machine) -> None:
    """Setup has no record of any tool set up by hand."""


def _claim_link_ticks_itself(root: Path, machine) -> None:
    """The wizard's console page marks `claim` done by itself once a session is linked."""
    agent.choose(root, ["console"])
    agent.mark(root, "console", "claim", progress.DONE)


def _a_step_marked_while_the_check_fails(root: Path, machine) -> None:
    """A working tool whose check is slow or failing at that instant isn't found."""
    machine.checks_pass = False
    agent.mark(root, "mail", "more-accounts", progress.SKIPPED)
    machine.checks_pass = True


def _the_window_builds_the_console_unpicked(root: Path, machine) -> None:
    """`setup ui` installs and builds the console, then a pick leaves it out."""
    ui_launch.launch(root)
    agent.choose(root, ["mail"])


def _a_found_tools_install_fails(root: Path, machine) -> None:
    """Save picks and install (`choose`, `auto`) on a found tool, whose install fails."""
    machine.returncode = 1
    agent.choose(root, ["mail"])
    run_automatic(root, ["mail"])
    machine.returncode = 0


def _a_found_tool_is_installed_again(root: Path, machine) -> None:
    """Save picks and install on a found tool with entries only its optional steps grant."""
    agent.choose(root, ["browser"])
    run_automatic(root, ["browser"])


def _a_found_tools_optional_step_is_skipped(root: Path, machine) -> None:
    """An optional step's Skip on a found tool's page: `setup mark`."""
    agent.mark(root, "mail", "more-accounts", progress.SKIPPED)


def _a_found_tools_step_runs_in_a_terminal(root: Path, machine) -> None:
    """Open a terminal on a found tool's step: `setup step`."""
    flow.run_one_step(root, "mail", "google-project")


def _a_found_tool_is_taken_on_then_skipped(root: Path, machine) -> None:
    """A step button on a found tool's page (`setup apply`), then it is left out of the picks."""
    agent.apply(root, "mail", "google-project", "yes", None)
    agent.choose(root, [])


@pytest.mark.parametrize(
    ("act", "tool_id", "status"),
    [
        (_nothing, "mail", ""),
        # A record appears without the owner handing the tool over: its entries stay theirs.
        (_claim_link_ticks_itself, "console", progress.STARTED),
        (_a_step_marked_while_the_check_fails, "mail", progress.STARTED),
        (_the_window_builds_the_console_unpicked, "console", progress.SKIPPED),
        # A found tool is taken on with its first step result, so the lists stay honest:
        # done when the step worked, failed when it didn't. Its entries stay the owner's.
        (_a_found_tools_install_fails, "mail", progress.FAILED),
        (_a_found_tool_is_installed_again, "browser", progress.DONE),
        (_a_found_tools_optional_step_is_skipped, "mail", progress.DONE),
        (_a_found_tools_step_runs_in_a_terminal, "mail", progress.DONE),
        (_a_found_tool_is_taken_on_then_skipped, "mail", progress.SKIPPED),
    ],
)
def test_wire_takes_out_only_what_it_added(
    tmp_path: Path, monkeypatch, machine, by_hand, act, tool_id, status
) -> None:
    # Regression: wire took every registry entry for setup's, then every entry of a tool
    # with a record, and so stripped servers, rules and hooks the owner had made by hand.
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    act(tmp_path, machine)
    for finished in ("brief", "usage"):  # two tools set up through setup, alongside
        assert agent.apply(tmp_path, finished, "install", None, None) == 0

    assert agent.wire(tmp_path, True) == 0

    added = ledger.load(tmp_path)
    saved = progress.load(tmp_path)
    assert progress.tool_status(saved, registry.by_id(tool_id), platforms.WINDOWS) == status
    # Every hand-made entry is as it was, and all that is new is in the ledger.
    assert by_hand.config() == by_hand.with_added(added)
    # The brief's entries are setup's. Usage's two hooks were there by hand (one sharing a
    # group, one in the checked-in settings), so they are neither added again nor claimed,
    # and nor is any server or rule the plan wants that the owner had already made.
    example = json.loads((tmp_path / ".mcp.example.json").read_text())["mcpServers"]
    assert added.servers == {"brief": example["brief"]}
    assert "mcp__brief" in added.allow and "brief" in added.enabled
    assert [record["hook"]["args"][-1] for record in added.hooks] == ["brief_tool.hooks.prompt"]

    # The owner edits the server setup added, and adds hooks of their own to the group
    # setup made: one new, one setup's with a changed value. A third is setup's very hook
    # under a matcher of theirs. Then they drop every tool.
    mcp_file, settings_file = by_hand.files
    mcp, settings = by_hand.config()
    edited_server = {**example["brief"], "env": {"MINE": "1"}}
    mcp["mcpServers"]["brief"] = edited_server
    mcp_file.write_text(json.dumps(mcp))
    groups = settings["hooks"]["UserPromptSubmit"]
    setup_hook = added.hooks[0]["hook"]
    edited_hook = {**setup_hook, "timeout": 5}
    groups[0]["hooks"] = [edited_hook, setup_hook, OWN_HOOK]
    groups.insert(0, {"matcher": "mine", "hooks": [setup_hook]})
    settings_file.write_text(json.dumps(settings))
    agent.choose(tmp_path, [])
    assert agent.wire(tmp_path, True) == 0

    # Only what setup added, still as setup wrote it, is gone: its hook, not the group the
    # owner's hooks share. An entry that differs from the ledger's (the server's or the
    # hook's value, the group's matcher) is the owner's: it stays, and leaves the ledger.
    by_hand_mcp, by_hand_settings = copy.deepcopy((by_hand.mcp, by_hand.settings))
    by_hand_mcp["mcpServers"]["brief"] = edited_server
    by_hand_settings["hooks"]["UserPromptSubmit"] = [
        {"matcher": "mine", "hooks": [setup_hook]},
        {"hooks": [edited_hook, OWN_HOOK]},
    ]
    assert by_hand.config() == (by_hand_mcp, by_hand_settings)
    assert ledger.load(tmp_path) == ledger.Ledger()
    assert by_hand.project_settings.read_bytes() == by_hand.project_bytes


def test_a_wire_with_nothing_to_add_or_take_out_writes_nothing(tmp_path: Path, machine) -> None:
    def snapshot() -> dict[Path, bytes]:
        return {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    # Files with none of the keys setup merges into: it mustn't add them empty either.
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.local.json").write_text('{"model":"opus"}')
    (tmp_path / ".mcp.json").write_text('{"mine":true}')
    (tmp_path / ".mcp.example.json").write_text('{"mcpServers": {}}')
    before = snapshot()

    assert agent.wire(tmp_path, True) == 0

    assert snapshot() == before  # byte for byte, and no .setup folder either


@pytest.mark.parametrize("ledger_text", [None, "{not json", "[]", '{"hooks": [3]}'])
def test_a_missing_or_unreadable_ledger_means_setup_added_nothing(
    tmp_path: Path, machine, by_hand, ledger_text
) -> None:
    assert agent.apply(tmp_path, "brief", "install", None, None) == 0
    assert agent.wire(tmp_path, True) == 0
    wired = by_hand.config()
    ledger_file = tmp_path / ledger.LEDGER_FILE
    ledger_file.unlink()
    if ledger_text is not None:
        ledger_file.write_text(ledger_text)

    agent.choose(tmp_path, [])  # the brief is skipped: the plan is empty
    assert agent.wire(tmp_path, True) == 0

    assert by_hand.config() == wired  # nothing is taken out, the brief's entries included


def test_a_status_line_setup_didnt_write_is_kept(tmp_path: Path, machine) -> None:
    # Regression: any status line running usage's module was replaced by setup's command.
    own = {"type": "command", "command": "py -m usage.statusline", "padding": 1}
    wiring.USER_SETTINGS.parent.mkdir(parents=True)
    wiring.USER_SETTINGS.write_text(json.dumps({"statusLine": own}))
    (tmp_path / ".mcp.example.json").write_text('{"mcpServers": {}}')
    data = progress.load(tmp_path)
    for step_id in ("install", "statusline"):
        progress.set_step(data, "usage", step_id, progress.DONE)
    plan = wiring.build_plan(registry.load(), data, platforms.WINDOWS)

    notes = wiring.apply_plan(tmp_path, plan, platforms.WINDOWS)

    assert json.loads(wiring.USER_SETTINGS.read_text()) == {"statusLine": own}
    assert len(notes) == 1 and ledger.load(tmp_path).statusline is None
