"""Finds tools that were set up by hand: working, in Claude Code's config, and unknown to setup.

Setup's lists (`setup status`, `status --json`, `list`) read .setup/progress.json, which says
nothing when the tools were installed before the setup window existed, the folder was lost,
or the checkout was copied to a machine that already had them. For a tool setup has no
record of (progress.has_record), this looks at the machine instead. The tool counts as set
up only when all of these hold:

- it has a verify command and registry `evidence` (local, gitignored paths), and every
  evidence path exists. A fresh clone has none, so nothing is run there; that matters, as a
  `uv run --no-sync` check would leave an empty venv behind.
- its servers and hooks are in Claude Code's config. `setup wire` adds only what the record
  lists, so "set up, not added yet" would offer a button that could never add it.
- its verify check passes, with its required steps taken as done.

Nothing here writes. The record a found tool is given lives in a copy of the progress,
never on disk, and `setup plan` and `setup wire` never see it: they grant only what the
owner picked and ran. The entries a found tool has in Claude Code's config were made by
hand, so they aren't in wire's ledger and wire never takes them out (wiring/ledger.py).

Setup takes a found tool on the first time a result is written for one of its steps:
record_to_adopt gives the record to start from, so re-running a step keeps the tool done.
That only keeps the lists honest; the tool's hand-made entries still aren't setup's.
"""

from pathlib import Path
from typing import Any, NamedTuple

from signal_setup import platforms, progress, registry, settings, verify, wiring
from signal_setup.registry import Tool

# What a found tool's row says after its check's words, so an Active row for a tool setup
# never ran explains itself.
FOUND_WORDS = "found already set up"

Records = dict[str, dict[str, Any]]


def _lacks_config(root: Path, tool: Tool, group: str) -> bool:
    """True when a config file of the tool's settings `group` was never made from its example."""
    schema = settings.load(tool.id)
    files = schema.files_in(group) if schema else ()
    return any(f.example and not (root / f.path).exists() for f in files)


def _assumed_record(root: Path, tool: Tool, platform: str) -> dict[str, Any]:
    """The record a finished setup would have left for `tool`.

    Required steps are done. An optional settings step whose config file isn't there is
    skipped (the tool runs on its defaults), so the check doesn't call that file missing;
    a config file that is there is still scanned for placeholders.
    """
    steps = {}
    for step in progress.applicable_steps(tool, platform):
        if not step.optional:
            steps[step.id] = progress.DONE
        elif step.kind == "settings" and _lacks_config(root, tool, step.group):
            steps[step.id] = progress.SKIPPED
    return {"skipped": False, "steps": steps}


def _with_records(data: dict[str, Any], records: Records) -> dict[str, Any]:
    """A copy of the progress with `records` (tool id to record) laid over its tools."""
    return {**data, "tools": {**data["tools"], **records}}


def _candidates(
    root: Path, tools: tuple[Tool, ...], data: dict[str, Any], platform: str
) -> Records:
    """The assumed record of each tool worth checking, by tool id. Reads files only.

    A candidate has no setup record, a verify command, every evidence path on disk, and
    its servers and hooks in Claude Code's config. Whether it is set up is then up to its
    check.
    """
    records = {
        tool.id: _assumed_record(root, tool, platform)
        for tool in tools
        if tool.verify
        and tool.evidence
        and not progress.has_record(data, tool.id)
        and all((root / path).exists() for path in tool.evidence)
    }
    # wired_tools also drops a tool the assumed record doesn't finish (only optional steps).
    wired = wiring.wired_tools(root, tools, _with_records(data, records), platform)
    return {tool_id: record for tool_id, record in records.items() if tool_id in wired}


class Found(NamedTuple):
    """What find() saw.

    Attributes:
        progress: The progress the lists read: the saved one, with a finished record laid
            over it for every tool found already set up.
        ids: The found tools' ids.
        checks: Every check find() ran, by tool id (a candidate's may have failed).
    """

    progress: dict[str, Any]
    ids: frozenset[str]
    checks: dict[str, verify.CheckResult]


def find(
    root: Path,
    data: dict[str, Any],
    timeout_s: float = verify.QUICK_TIMEOUT_S,
    with_finished: bool = False,
) -> Found:
    """Find the tools set up by hand: run each candidate's check and keep those that pass.

    Args:
        root: The repo root.
        data: The saved progress (progress.load); never changed.
        timeout_s: The cap on each check. They all run at once, so this is the whole wait.
        with_finished: Also check every tool the record says is finished, in the same
            round (`setup status --json` wants those too, and must not wait twice).

    Returns:
        The progress to read, the found tools' ids and the checks that ran. A candidate
        whose check failed stays as the record has it.
    """
    tools, platform = registry.load(), platforms.current()
    records = _candidates(root, tools, data, platform)
    to_check = [
        tool
        for tool in tools
        if tool.id in records
        or (with_finished and progress.tool_status(data, tool, platform) == progress.DONE)
    ]
    # Checked as if every candidate were finished: its assumed record sets which config counts.
    checks = verify.check_all(root, to_check, _with_records(data, records), timeout_s)
    found = {tool_id: record for tool_id, record in records.items() if checks[tool_id].passed}
    return Found(_with_records(data, found), frozenset(found), checks)


def record_to_adopt(root: Path, tool: Tool, data: dict[str, Any]) -> dict[str, Any] | None:
    """The record to start `tool` from when it reads as found right now, else None.

    For the writers of a step's result (progress.adopt): a found tool's first result must
    land on the record its detection assumed (required steps done, an optional settings
    step with no config skipped), or one step would leave it reading half set up. Runs the
    tool's check, and only when it has no record, its evidence and its wiring. A tool that
    is merely unrecorded gets None and starts a plain record.

    Args:
        root: The repo root.
        tool: The tool a step result is about to be written for.
        data: The saved progress; never changed.
    """
    records = _candidates(root, (tool,), data, platforms.current())
    if tool.id not in records:
        return None
    check = verify.check(root, tool, _with_records(data, records), verify.QUICK_TIMEOUT_S)
    return records[tool.id] if check.passed else None
