"""Routes each tool call the board agent wants to make: auto-allow, or ask the owner.

Auto-allowed: every whiteboard MCP tool but the two that tick or untick a todo in
the owner's life/ files (those ask, since the board is untrusted), audiohub's `notify`, `ToolSearch`
(the CLI defers MCP tool schemas, so the agent must load them before drawing),
and a Read of exactly this turn's snapshot PNG (the image fallback). Everything else,
including every other file read, goes to a blocking yes/no question (the
signal_confirm Allow/Deny dialog in production), one at a time, denied on any
failure. Classifying paths as safe proved bypassable (Windows aliases, Grep
globs), so there is none: only an exact string match passes. This module knows
nothing about the SDK.
"""

import asyncio
import json
import logging
import os
import re
from collections.abc import Callable, Mapping
from pathlib import Path

from signal_confirm import elide

logger = logging.getLogger(__name__)

# Claude Code names MCP tools "mcp__<server>__<tool>". A server named
# "whiteboard__x" would also start with the prefix, so the part after it must be
# plain snake_case words (no double or leading underscore), like our tool names.
WHITEBOARD_TOOL_PATTERN = re.compile(r"mcp__whiteboard__[A-Za-z0-9-]+(?:_[A-Za-z0-9-]+)*")
# ToolSearch only loads tool schemas (MCP tools are deferred in the bundled CLI);
# it reads no files and runs nothing, and without it no whiteboard tool is callable.
AUTO_ALLOWED_TOOLS = frozenset({"mcp__audiohub__notify", "ToolSearch"})
# Anyone in the room can write on the board, so these need the owner's OK:
# - the TODO ticks write to the owner's KB ("mark it all done"; a cross-out on the board ticks
#   items without the agent);
# - the night view is sleep mode's: showing it pauses the board's watching, and hiding
#   it lights up the room while the owner sleeps.
ASK_FIRST_WHITEBOARD_TOOLS = frozenset(
    {
        "mcp__whiteboard__board_todo_done",
        "mcp__whiteboard__board_todo_undone",
        "mcp__whiteboard__board_night_show",
        "mcp__whiteboard__board_night_hide",
    }
)
SNAPSHOT_READ_TOOL = "Read"

DIALOG_CAPTION = "Whiteboard agent: allow this?"
# Long tool inputs (a whole Write body) are cut so the dialog stays readable, but
# both ends are shown: a harmful command can hide at the end of a long input.
# elide() splits this into 500 characters of head and 250 of tail around the
# 3-character ellipsis.
MAX_INPUT_CHARS = 753

AskYesNo = Callable[[str], bool]
"""Blocks until the owner answers; returns True for yes. Runs in a worker thread."""


def is_auto_allowed(
    tool_name: str, tool_input: Mapping[str, object], snapshot_path: str | None
) -> bool:
    """Say whether a tool call may run without asking.

    Args:
        tool_name: The tool, e.g. "Read" or "mcp__whiteboard__board_draw".
        tool_input: The tool's input as Claude sent it.
        snapshot_path: This turn's snapshot, from normalize_path(), or None.

    Returns:
        True for whiteboard tools (except ASK_FIRST_WHITEBOARD_TOOLS), audiohub notify,
        ToolSearch, and a Read whose file_path is exactly the snapshot path.
    """
    if tool_name in ASK_FIRST_WHITEBOARD_TOOLS:
        return False
    if WHITEBOARD_TOOL_PATTERN.fullmatch(tool_name) or tool_name in AUTO_ALLOWED_TOOLS:
        return True
    file_path = tool_input.get("file_path")
    if tool_name != SNAPSHOT_READ_TOOL or snapshot_path is None or not isinstance(file_path, str):
        return False
    return os.path.isabs(file_path) and normalize_path(file_path) == snapshot_path


def normalize_path(path: str) -> str:
    """Normalize an absolute path as a string only (no filesystem calls).

    Windows aliases such as a trailing dot, "::$DATA" or an 8.3 name stay
    different strings, so they don't match and fall through to the dialog.
    """
    return os.path.normcase(os.path.normpath(path))


def describe_request(tool_name: str, tool_input: Mapping[str, object]) -> str:
    """Build the dialog text for one tool call.

    Args:
        tool_name: The tool's name.
        tool_input: The tool's input.

    Returns:
        A short question naming the tool and showing its (truncated) input.
    """
    shown = elide(json.dumps(tool_input, indent=1, default=str), MAX_INPUT_CHARS)
    return f"The whiteboard agent wants to run {tool_name}:\n\n{shown}\n\nAllow it?"


class PermissionRouter:
    """Decides tool calls for the board agent's session."""

    def __init__(self, ask_yes_no: AskYesNo) -> None:
        """Create the router.

        Args:
            ask_yes_no: Asks the owner. It must time out on its own (the
                dialog denies after 120 s), or the turn waits for it.
        """
        self._ask_yes_no = ask_yes_no
        self._snapshot_path: str | None = None
        # The SDK decides parallel tool calls in parallel tasks; one dialog at a time.
        self._dialog_lock = asyncio.Lock()

    def allow_snapshot_read(self, png_path: Path) -> None:
        """Let the coming turn Read its own snapshot without asking (replaces the last one)."""
        self._snapshot_path = normalize_path(str(png_path))

    async def decide(
        self, tool_name: str, tool_input: Mapping[str, object], blocked_path: str | None = None
    ) -> bool:
        """Decide one tool call.

        Args:
            tool_name: The tool's name.
            tool_input: The tool's input.
            blocked_path: A path the CLI flagged as outside the allowed folders, if
                any; such a call is always asked about.

        Returns:
            True to allow. False when the owner says no, the dialog times out, or
            asking fails (failing closed is the safe default).
        """
        if blocked_path is None and is_auto_allowed(tool_name, tool_input, self._snapshot_path):
            logger.debug("Auto-allowed %s", tool_name)
            return True
        question = describe_request(tool_name, tool_input)
        async with self._dialog_lock:
            logger.info("Asking the owner to approve %s", tool_name)
            try:
                is_approved = await asyncio.to_thread(self._ask_yes_no, question)
            except Exception:
                logger.exception("Permission dialog failed for %s; denying", tool_name)
                return False
        logger.info("Owner %s %s", "allowed" if is_approved else "denied", tool_name)
        return bool(is_approved)
