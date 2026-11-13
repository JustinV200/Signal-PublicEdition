"""generate_keynotes: ask Claude for today's keynote lines and save them.

One tool-less, single-turn call through the agent package's ask_sdk (the same path
the board's triage and cross-out checks use: the Claude Code CLI, no settings files).
The reply must be {"lines": [...]} with 1 to MAX_LINES strings; anything else is a
KeynotesError and the old file is left alone (a stale file shows nothing anyway).
Run by `whiteboard keynotes` (the 06:00 scheduled task, or on demand).
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Any

from whiteboard.agent import ask_sdk, stream_message
from whiteboard.keynotes.prompt import SYSTEM_PROMPT, build_message, gather_day
from whiteboard.keynotes.store import clean_lines, write_keynotes

# The latest Sonnet; the CLI resolves the alias.
MODEL = "sonnet"
TIMEOUT_S = 180.0

# (user message, model, system prompt) -> (reply text, cost in USD or None), like ask_sdk.
Ask = Callable[[dict[str, Any], str, str], Awaitable[tuple[str, float | None]]]


class KeynotesError(RuntimeError):
    """The model's reply wasn't usable keynotes."""


async def generate_keynotes(
    life_dir: Path, today: date, paths: tuple[Path, Path], ask: Ask | None = None
) -> tuple[str, ...]:
    """Ask the model for `today`'s keynotes and write them to the keynotes file.

    Args:
        life_dir: The owner's KB.
        today: The day they're for.
        paths: (the TODO view's done-tracking file, the keynotes file to write).
        ask: Runs the model call; tests pass a fake. Defaults to the real SDK.

    Returns:
        The lines written.

    Raises:
        KeynotesError: The reply wasn't {"lines": [...]} with at least one line.
        TimeoutError: The call took over TIMEOUT_S.
        OSError: A plan can't be read or the file can't be written.
    """
    state_path, keynotes_path = paths
    day = await asyncio.to_thread(gather_day, life_dir, today, state_path)
    ask = ask or ask_sdk
    message = stream_message([{"type": "text", "text": build_message(day)}])
    text, _cost = await asyncio.wait_for(ask(message, MODEL, SYSTEM_PROMPT), TIMEOUT_S)
    lines = parse_lines(text)
    await asyncio.to_thread(write_keynotes, keynotes_path, today, lines, MODEL)
    return lines


def parse_lines(text: str) -> tuple[str, ...]:
    """The cleaned lines from the model's JSON reply.

    Raises:
        KeynotesError: Not JSON {"lines": [str, ...]}, or no line left after cleaning.
    """
    # The model sometimes wraps JSON in a code fence; take the outermost object.
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start : end + 1]) if start >= 0 else None
    except (ValueError, RecursionError) as error:
        raise KeynotesError(f"reply isn't JSON: {error}") from error
    lines = data.get("lines") if isinstance(data, dict) else None
    if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
        raise KeynotesError('reply isn\'t {"lines": [...]} with text lines')
    cleaned = clean_lines(lines)
    if not cleaned:
        raise KeynotesError("reply had no lines")
    return cleaned
