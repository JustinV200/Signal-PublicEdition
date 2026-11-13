"""Parses claude's final `result` event into a validated RunResult.

The event's `structured_output` follows schema.py, but the model wrote it after
reading untrusted email, so every field is checked and capped here before the runner
logs any of it. A malformed entry is dropped and counted.
"""

from collections.abc import Callable
from dataclasses import dataclass

from mail_digest.claude.fields import is_email, is_message_id
from mail_digest.claude.launcher import ClaudeRun
from mail_digest.settings import MAX_OUTPUT_ITEMS, MAX_SUMMARY_CHARS

SUCCESS_SUBTYPE = "success"


@dataclass(frozen=True)
class SuspiciousEmail:
    """An email that tried to steer the job. Only these three checked fields are kept."""

    alias: str
    message_id: str
    sender: str


@dataclass(frozen=True)
class RunResult:
    """One run's outcome as the runner sees it.

    is_success: the run finished normally with a structured output.
    dropped: model entries dropped as malformed or over the cap.
    denials: one "tool path" string per tool call the permission layer refused.
    claude_version: from claude's init event.
    error: why the run isn't a success ("" when it is).
    """

    is_success: bool
    suspicious: tuple[SuspiciousEmail, ...] = ()
    summary: str = ""
    dropped: int = 0
    cost_usd: float | None = None
    denials: tuple[str, ...] = ()
    claude_version: str = ""
    error: str = ""


def parse_result(run: ClaudeRun, aliases: tuple[str, ...]) -> RunResult:
    """Validate one run. Never raises: a bad or missing result is a failed RunResult."""
    raw = run.result or {}
    common = {
        "cost_usd": run_cost(run),
        "denials": _denials(raw.get("permission_denials")),
        "claude_version": run.version,
    }
    output, error = structured_output(run)
    if output is None:
        return RunResult(is_success=False, error=error, **common)
    suspicious, dropped = _parse_list(output, "suspicious", _suspicious(aliases))
    return RunResult(
        is_success=True,
        suspicious=suspicious,
        summary=str(output.get("summary", ""))[:MAX_SUMMARY_CHARS],
        dropped=dropped,
        **common,
    )


def structured_output(run: ClaudeRun) -> tuple[dict | None, str]:
    """(the run's structured output, "") on a normal finish, else (None, why not).

    Never raises. The output is still the model's: the caller validates every field.
    """
    raw = run.result or {}
    if run.error:
        return None, run.error
    output = raw.get("structured_output")
    if raw.get("subtype") != SUCCESS_SUBTYPE or raw.get("is_error") or not isinstance(output, dict):
        why = f"run ended with subtype={raw.get('subtype')!r} is_error={raw.get('is_error')!r}"
        return None, why
    return output, ""


def run_cost(run: ClaudeRun) -> float | None:
    """The run's total_cost_usd, or None if it didn't report one."""
    cost = (run.result or {}).get("total_cost_usd")
    return float(cost) if isinstance(cost, int | float) else None


def _parse_list[T](
    output: dict, name: str, parse_item: Callable[[dict], T | None]
) -> tuple[tuple[T, ...], int]:
    """(valid items of output[name], how many were dropped), at most MAX_OUTPUT_ITEMS kept."""
    value = output.get(name)
    items = value if isinstance(value, list) else []
    parsed = [parse_item(item) if isinstance(item, dict) else None for item in items]
    kept = [item for item in parsed if item is not None][:MAX_OUTPUT_ITEMS]
    return tuple(kept), len(items) - len(kept)


def _suspicious(aliases: tuple[str, ...]) -> Callable[[dict], SuspiciousEmail | None]:
    """A parser for one suspicious entry: known alias, Gmail id, bare sender address."""

    def parse(item: dict) -> SuspiciousEmail | None:
        alias, message_id, sender = item.get("alias"), item.get("message_id"), item.get("sender")
        if alias not in aliases or not isinstance(message_id, str) or not isinstance(sender, str):
            return None
        if not (is_message_id(message_id) and is_email(sender)):
            return None
        return SuspiciousEmail(alias, message_id, sender)

    return parse


def _denials(value: object) -> tuple[str, ...]:
    """Readable "tool path" lines from claude's permission_denials list."""
    if not isinstance(value, list):
        return ()
    lines = []
    for denial in value:
        if not isinstance(denial, dict):
            continue
        tool_input = denial.get("tool_input")
        target = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
        lines.append(f"{denial.get('tool_name', '?')} {target}".strip())
    return tuple(lines)
