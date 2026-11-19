"""Each tool's live health for System's Tools list: active, down or not set up, and wired.

`setup status --json` prints health_rows(). Every finished tool runs its verify command with
a short timeout, and so does every tool that looks set up by hand (detect.py), all at once
in threads, so the page stays quick to refresh. A tool found that way reads like a finished
one, and its words say so.
"""

from pathlib import Path
from typing import Any

from signal_setup import detect, platforms, progress, registry, verify, wiring

ACTIVE, DOWN, NOT_SET_UP = "active", "down", "not_set_up"
HEALTH_TIMEOUT_S = verify.QUICK_TIMEOUT_S


def classify(setup_status: str, check: verify.CheckResult | None) -> tuple[str, verify.CheckResult]:
    """The health state and what to show from a tool's setup status and its check.

    Args:
        setup_status: progress.tool_status (done, skipped, failed, started or ''), read from
            the progress with the tools found already set up laid over it, so a found tool
            comes in as done. One that isn't found keeps what the record says, never down.
        check: verify.check's result; only looked at when setup is done.

    Returns:
        (ACTIVE | DOWN | NOT_SET_UP, the result whose words, fix and command the row shows).
    """
    if setup_status != progress.DONE:
        # Never picked: no words, so the row reads "Not set up" once, not "· never set up".
        words = {
            progress.SKIPPED: "skipped",
            "": "",
            progress.STARTED: "setup started, not finished",
            progress.FAILED: "a setup step failed",
        }.get(setup_status, setup_status)
        return NOT_SET_UP, verify.CheckResult(False, words)
    result = check if check is not None else verify.CheckResult(False, "not checked")
    return (ACTIVE if result.passed else DOWN), result


def health_rows(root: Path, timeout_s: float = HEALTH_TIMEOUT_S) -> list[dict[str, Any]]:
    """One row per registry tool: id, name, platform, setup status, state, words, fix,
    command, wired and detected.

    `wired` is True when a finished tool's servers and hooks are in Claude Code's config
    (read only, wiring.wired_tools); the page shows a finished tool that isn't wired as
    "not added to Claude Code yet", never as Active. `detected` is True for a tool setup
    has no record of that was found already set up (detect.py): it reads as done, and its
    words end with detect.FOUND_WORDS.
    """
    platform = platforms.current()
    # One round of checks: the finished tools and the ones that look set up by hand.
    data, found, checks = detect.find(root, progress.load(root), timeout_s, with_finished=True)
    tools = registry.load()
    wired = wiring.wired_tools(root, tools, data, platform)
    rows = []
    for tool in tools:
        status = progress.tool_status(data, tool, platform)
        state, result = classify(status, checks.get(tool.id))
        is_found = tool.id in found
        rows.append(
            {
                "id": tool.id,
                "name": tool.name,
                "platform": platforms.label(tool),
                "supported_here": platforms.is_supported(tool, platform),
                "setup_status": status or "not set up",
                "state": state,
                # words, fix and command, as in the console's own health rows (which also
                # have level and state); a check's `output` stays out of the page.
                "words": f"{result.words} · {detect.FOUND_WORDS}" if is_found else result.words,
                "fix": result.fix,
                "command": result.command,
                "wired": tool.id in wired,
                "detected": is_found,
            }
        )
    return rows
