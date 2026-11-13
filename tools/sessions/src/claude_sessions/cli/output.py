"""Plain-text rendering of daemon results and repo listings for the terminal.

The daemon returns JSON-ready dicts (see daemon.session.views); these
functions turn them into short, aligned lines for a person.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from claude_sessions.repos import Repo

COST_FORMAT = "${:.4f}"
REPLY_INDENT = "    "


def format_summary_line(summary: Mapping[str, Any]) -> str:
    """One line for a session in `sessions list`.

    Args:
        summary: A session summary from the daemon.

    Returns:
        E.g. "s-1a2b3c4d  idle (live)  OtherRepo  $0.0123  2026-10-19 15:42:07".
    """
    liveness = " (live)" if summary.get("is_live") else ""
    cost = COST_FORMAT.format(summary.get("cost_usd") or 0.0)
    return (
        f"{summary['id']}  {summary['state']}{liveness}  {summary['repo']}  {cost}  "
        f"{summary.get('updated_at', '')}"
    )


def format_status(status: Mapping[str, Any]) -> str:
    """Several lines for `sessions status`: summary, details, then the newest replies.

    Args:
        status: A session status from the daemon.

    Returns:
        The text to print.
    """
    lines = [
        format_summary_line(status),
        f"  repo path:      {status['repo_path']}",
        f"  claude session: {status['claude_session_id']}",
        f"  model / mode:   {status.get('model') or 'default'} / {status['permission_mode']}",
    ]
    if status.get("pending_approval"):
        lines.append(f"  waiting for approval: {status['pending_approval']}")
    if status.get("error"):
        lines.append(f"  error: {status['error']}")
    lines.extend(_reply_lines(status.get("last_texts") or []))
    return "\n".join(lines)


def format_sessions(summaries: Sequence[Mapping[str, Any]]) -> str:
    """All of `sessions list`, or a hint when there are none."""
    if not summaries:
        return "No managed sessions yet. Start one with: sessions start REPO PROMPT"
    return "\n".join(format_summary_line(summary) for summary in summaries)


def format_repos(repos: Sequence[Repo]) -> str:
    """`sessions repos`: names padded into a column, then paths."""
    if not repos:
        return "No git repos found under the configured roots."
    width = max(len(repo.name) for repo in repos)
    return "\n".join(f"{repo.name.ljust(width)}  {repo.path}" for repo in repos)


def _reply_lines(texts: Iterable[str]) -> list[str]:
    """The newest replies, each indented under a header."""
    lines: list[str] = []
    for text in texts:
        lines.append("  reply:")
        lines.extend(f"{REPLY_INDENT}{line}" for line in text.splitlines() or [""])
    return lines
