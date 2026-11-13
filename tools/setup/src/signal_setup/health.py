"""Each tool's live health for the console's Tools page: active, down or not set up.

`setup status --json` prints health_rows(). A finished tool runs its verify command with a
short timeout (all tools at once, in threads), so the page stays quick to refresh.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from signal_setup import platforms, progress, registry, verify

ACTIVE, DOWN, NOT_SET_UP = "active", "down", "not_set_up"
# Short on purpose: the page waits on the slowest check, and a hung daemon reads as down.
HEALTH_TIMEOUT_S = 8


def classify(setup_status: str, check: tuple[bool, str] | None) -> tuple[str, str]:
    """The health state and a detail line from a tool's setup status and its check.

    Args:
        setup_status: progress.tool_status (done, skipped, failed, started or '').
        check: (passed, detail) from verify.check; only looked at when setup is done.

    Returns:
        (ACTIVE | DOWN | NOT_SET_UP, detail words).
    """
    if setup_status != progress.DONE:
        detail = {
            progress.SKIPPED: "skipped",
            "": "never set up",
            "started": "setup started, not finished",
            progress.FAILED: "a setup step failed",
        }.get(setup_status, setup_status)
        return NOT_SET_UP, detail
    passed, detail = check if check is not None else (False, "not checked")
    return (ACTIVE if passed else DOWN), detail


def health_rows(root: Path, timeout_s: float = HEALTH_TIMEOUT_S) -> list[dict[str, Any]]:
    """One row per registry tool: id, name, platform, setup status, state and detail."""
    data, platform = progress.load(root), platforms.current()
    tools = registry.load()
    statuses = {t.id: progress.tool_status(data, t, platform) for t in tools}
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
        state, detail = classify(statuses[tool.id], checks.get(tool.id))
        rows.append(
            {
                "id": tool.id,
                "name": tool.name,
                "platform": platforms.label(tool),
                "supported_here": platforms.is_supported(tool, platform),
                "setup_status": statuses[tool.id] or "not set up",
                "state": state,
                "detail": detail,
            }
        )
    return rows
