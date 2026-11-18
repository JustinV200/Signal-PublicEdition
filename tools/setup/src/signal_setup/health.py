"""Each tool's live health for System's Tools list: active, down or not set up, and wired.

`setup status --json` prints health_rows(). A finished tool runs its verify command with a
short timeout (all tools at once, in threads), so the page stays quick to refresh.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from signal_setup import platforms, progress, registry, verify, wiring

ACTIVE, DOWN, NOT_SET_UP = "active", "down", "not_set_up"
# Short on purpose: the page waits on the slowest check, and a hung daemon reads as down.
HEALTH_TIMEOUT_S = 8


def classify(setup_status: str, check: verify.CheckResult | None) -> tuple[str, verify.CheckResult]:
    """The health state and what to show from a tool's setup status and its check.

    Args:
        setup_status: progress.tool_status (done, skipped, failed, started or '').
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
    command and wired.

    `wired` is True when a finished tool's servers and hooks are in Claude Code's config
    (read only, wiring.wired_tools); the page shows a finished tool that isn't wired as
    "not added to Claude Code yet", never as Active.
    """
    data, platform = progress.load(root), platforms.current()
    tools = registry.load()
    statuses = {t.id: progress.tool_status(data, t, platform) for t in tools}
    wired = wiring.wired_tools(root, tools, data, platform)
    done = [t for t in tools if statuses[t.id] == progress.DONE]
    with ThreadPoolExecutor(max_workers=max(1, len(done))) as pool:
        checks = dict(
            zip(
                (t.id for t in done),
                pool.map(lambda t: verify.check(root, t, data, timeout_s), done),
                strict=True,
            )
        )
    rows = []
    for tool in tools:
        state, result = classify(statuses[tool.id], checks.get(tool.id))
        rows.append(
            {
                "id": tool.id,
                "name": tool.name,
                "platform": platforms.label(tool),
                "supported_here": platforms.is_supported(tool, platform),
                "setup_status": statuses[tool.id] or "not set up",
                "state": state,
                # words, fix and command, as in the console's own health rows (which also
                # have level and state); a check's `output` stays out of the page.
                "words": result.words,
                "fix": result.fix,
                "command": result.command,
                "wired": tool.id in wired,
            }
        )
    return rows
