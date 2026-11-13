"""Find a session's brief deliveries in its transcript, and Claude's replies after each.

A Claude Code transcript is JSON lines. A delivery is found only where it really
reached Claude, and only as the id opening its trusted line ("Signal brief
b-<hash>.<n>, ..."), never inside a frame or other text:
- a prompt hook injection: an "attachment" record of type hook_additional_context
  whose hookName and hookEvent are both UserPromptSubmit (the CLI also writes
  prompt.mention attachments with that hookEvent), for ids this session's hook
  recorded;
- a brief_me result: a tool_result answering this transcript's own
  mcp__brief__brief_me call. An id in a prompt, mail or another tool's output
  never counts.
Replies are the main thread's assistant text blocks only: no thinking, tool calls
or tool results.
"""

import json
import mmap
import os
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from signal_brief import BRIEF_ID_HASH_CHARS

from brief_tool.wording import DELIVERY_LINE_PREFIX

BRIEF_ME_TOOL = "mcp__brief__brief_me"
# The id (b-<hash>.<n>) at the start of a delivery's trusted line (brief_tool.wording).
DELIVERY_LINE = re.compile(
    rf"^{re.escape(DELIVERY_LINE_PREFIX)}(b-[0-9a-f]{{{BRIEF_ID_HASH_CHARS}}}\.\d+)\b",
    re.MULTILINE,
)
HOOK_ATTACHMENT = "hook_additional_context"
HOOK_EVENT = "UserPromptSubmit"


def replies_after_deliveries(
    transcript: Path, hook_ids: set[str], tool_ids: set[str]
) -> dict[str, list[str]]:
    """For each wanted delivery found in `transcript`, Claude's reply text after it.

    Args:
        transcript: The session's transcript_path.
        hook_ids: Delivery ids this session's prompt hook injected.
        tool_ids: Delivery ids brief_me returned (to some session).

    Returns:
        Delivery id -> assistant text blocks after it, in order. Ids not found are absent.

    Raises:
        OSError: The transcript couldn't be read.
    """
    ids = hook_ids | tool_ids
    # Most prompts have nothing pending in this session: skip parsing a large file.
    if not _mentions_any(transcript, ids):
        return {}
    found: dict[str, int] = {}
    replies: list[tuple[int, str]] = []
    brief_me_calls: set[str] = set()
    for index, record in _records(transcript, ids, lambda: bool(found)):
        kind = record.get("type")
        if kind == "assistant":
            texts = _assistant_texts(record, brief_me_calls)
            # Text from before the first delivery is never anyone's reply: don't keep it.
            replies += [(index, text) for text in texts] if found else []
        elif kind == "user":
            _note(found, _brief_me_results(record, brief_me_calls), tool_ids, index)
        elif kind == "attachment":
            _note(found, _hook_context(record), hook_ids, index)
    return {
        delivery_id: [text for at, text in replies if at > position]
        for delivery_id, position in found.items()
    }


def _mentions_any(transcript: Path, ids: set[str]) -> bool:
    """Whether any id is in the file, searched via mmap rather than read into memory."""
    with transcript.open("rb") as file:
        if os.fstat(file.fileno()).st_size == 0:  # mmap can't map an empty file
            return False
        with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            return any(mapped.find(i.encode()) != -1 for i in ids)


def _records(
    transcript: Path, ids: set[str], replies_wanted: Callable[[], bool]
) -> Iterator[tuple[int, dict[str, Any]]]:
    """The transcript's readable main-thread records that matter, with their line numbers.

    Streamed line by line. Only lines that could hold a delivery or a brief_me call
    are parsed, plus assistant lines once `replies_wanted()` says a delivery was found.
    """
    keys = [i.encode() for i in ids] + [BRIEF_ME_TOOL.encode()]
    with transcript.open("rb") as file:
        for index, line in enumerate(file):
            wanted = any(key in line for key in keys)
            if not wanted and not (replies_wanted() and b'"assistant"' in line):
                continue
            try:
                record = json.loads(line.decode("utf-8", errors="replace"))
            except ValueError:
                continue
            if isinstance(record, dict) and not record.get("isSidechain"):
                yield index, record


def _blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return (
        [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []
    )


def _assistant_texts(record: dict[str, Any], brief_me_calls: set[str]) -> list[str]:
    """The record's text blocks; also notes any brief_me call it makes."""
    texts = []
    for block in _blocks(record):
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            texts.append(block["text"])
        elif block.get("type") == "tool_use" and block.get("name") == BRIEF_ME_TOOL:
            brief_me_calls.add(str(block.get("id")))
    return texts


def _brief_me_results(record: dict[str, Any], brief_me_calls: set[str]) -> str:
    """The text of every tool_result in the record that answers a brief_me call."""
    texts = []
    for block in _blocks(record):
        if block.get("type") == "tool_result" and block.get("tool_use_id") in brief_me_calls:
            content = block.get("content")
            parts = content if isinstance(content, list) else [{"text": content}]
            texts += [str(part.get("text", "")) for part in parts if isinstance(part, dict)]
    return "\n".join(texts)


def _hook_context(record: dict[str, Any]) -> str:
    """The text a UserPromptSubmit hook added, if this attachment is one."""
    attachment = record.get("attachment")
    if not isinstance(attachment, dict) or attachment.get("type") != HOOK_ATTACHMENT:
        return ""
    if attachment.get("hookEvent") != HOOK_EVENT or attachment.get("hookName") != HOOK_EVENT:
        return ""
    content = attachment.get("content")
    return "\n".join(str(part) for part in content) if isinstance(content, list) else str(content)


def _note(found: dict[str, int], text: str, wanted: set[str], index: int) -> None:
    """Record where each wanted id opening a trusted line of `text` first appears."""
    for delivery_id in DELIVERY_LINE.findall(text):
        if delivery_id in wanted:
            found.setdefault(delivery_id, index)
