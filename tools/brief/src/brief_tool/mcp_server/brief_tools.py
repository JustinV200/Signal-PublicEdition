"""BriefTools: the behaviour behind the brief_* MCP tools (away_* is in away_tools.py).

Every result with outside text in it is one trusted line plus one frame
(signal_untrusted).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from signal_brief import (
    BRIEF_TAG,
    ERROR_QUOTE_CHARS,
    BriefPaths,
    DeliveryOrigin,
    Entry,
    NewEntry,
    append_entry,
    away_status,
    compose,
    current_entries,
    entry_model_data,
    find_entry,
    local_now,
    record_delivery,
    render_model,
    resolve_entry,
)
from signal_untrusted import framed, safe_json

from brief_tool.mcp_server.calls import call_in_thread
from brief_tool.surface import MANAGED
from brief_tool.wording import (
    ACK_IN_SESSION,
    ACK_REFUSED_MANAGED,
    BRIEF_ME_AWAY_LINE,
    BRIEF_ME_LINE,
    ENTRY_LINE,
    NOTHING_NEW,
    UNDO_LINE,
)


class BriefTools:
    """Backs every brief MCP tool. Parameters are named as the tools' schemas show them."""

    def __init__(
        self, paths: BriefPaths, surface: str, clock: Callable[[], datetime] = local_now
    ) -> None:
        """Configure the tools.

        Args:
            paths: The brief's state files.
            surface: "session" or "managed" (brief_tool.surface).
            clock: The current time; tests pass a fixed one.
        """
        self._paths = paths
        self._surface = surface
        self._clock = clock

    async def brief_me(self, kind: str = "general") -> str:
        """See descriptions.BRIEF_ME."""
        return await call_in_thread(self._brief_me, kind)

    async def brief_ack(self, delivery_id: str) -> str:
        """See descriptions.BRIEF_ACK. In a session it never acks (the prompt hook does)."""
        if self._surface == MANAGED:
            raise ToolError(ACK_REFUSED_MANAGED)
        return ACK_IN_SESSION

    async def brief_log(
        self,
        kind: str,
        title: str,
        key: str = "",
        detail: str = "",
        undo: dict[str, Any] | None = None,
        priority: str = "normal",
        untrusted: bool = False,
    ) -> str:
        """See descriptions.BRIEF_LOG."""
        new = NewEntry(kind, title, key, detail, undo, priority, untrusted, self._surface)
        entry = await call_in_thread(append_entry, self._paths, new, self._clock())
        return f"Logged as {entry.ref}."

    async def brief_resolve(self, key_or_ref: str) -> str:
        """See descriptions.BRIEF_RESOLVE."""
        entry = await call_in_thread(resolve_entry, self._paths, key_or_ref, self._clock())
        return f"Resolved {entry.ref}."

    async def brief_get(self, ref: str) -> str:
        """See descriptions.BRIEF_GET."""
        entry = await call_in_thread(self._find, ref)
        data = entry_model_data(entry) | {"kind": entry.content.kind, "resolved": entry.resolved}
        return framed(ENTRY_LINE.format(ref=entry.ref), data, BRIEF_TAG)

    async def brief_undo(self, ref: str) -> str:
        """See descriptions.BRIEF_UNDO. The action goes outside the frame, the title inside."""
        entry = await call_in_thread(self._find, ref)
        undo = entry.content.undo
        if undo is None or entry.content.untrusted:
            raise ToolError(f"{entry.ref} has no undo action")
        # safe_json escapes "<" like the frame does, so the action can't fake a frame boundary.
        line = UNDO_LINE.format(ref=entry.ref, action=safe_json(undo))
        return framed(line, {"ref": entry.ref, "title": entry.content.title}, BRIEF_TAG)

    def _brief_me(self, kind: str) -> str:
        brief = compose(self._paths, kind)
        if not brief.items:
            return NOTHING_NEW
        render = render_model(brief)
        now = self._clock()
        if away_status(self._paths, now).is_away:
            # No delivery: a reply the owner doesn't see overnight mustn't ack it at the owner's
            # next prompt.
            return framed(BRIEF_ME_AWAY_LINE, render.body, BRIEF_TAG)
        origin = DeliveryOrigin(self._surface)
        delivery = record_delivery(self._paths, brief, render, origin, now)
        return framed(BRIEF_ME_LINE.format(delivery_id=delivery.id), render.body, BRIEF_TAG)

    def _find(self, ref: str) -> Entry:
        entry = find_entry(current_entries(self._paths), ref)
        if entry is None:
            raise ValueError(f"no brief item {ref[:ERROR_QUOTE_CHARS]!r}")
        return entry
