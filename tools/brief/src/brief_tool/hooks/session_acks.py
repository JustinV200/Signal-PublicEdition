"""ack_session_deliveries: on a present prompt, ack what Claude passed on in this session.

The owner's prompt after a brief means the owner read Claude's reply, so each of this
session's unseen deliveries (its own hook injections, and brief_me results found
in its transcript) is acked by the ref rule: through the seq just before the
oldest ref past the bookmark that Claude's replies since left out. A delivery none
of whose refs were passed on isn't acked at all, so an ignored brief stays due.
"""

from datetime import datetime
from pathlib import Path

from signal_brief import BriefPaths, ack_delivery, load_deliveries, read_through, relayed_through

from brief_tool.hooks.transcript import replies_after_deliveries
from brief_tool.surface import SESSION


def ack_session_deliveries(
    paths: BriefPaths, session_id: str, transcript: Path | None, now: datetime
) -> int:
    """Ack this session's unseen deliveries by what Claude's replies relayed.

    Args:
        paths: The brief's state files.
        session_id: This Claude session's id.
        transcript: Its transcript_path, or None if the hook wasn't given one.
        now: The time of the prompt.

    Returns:
        How many deliveries were acked further.

    Raises:
        BriefLogError: The brief's state couldn't be read or written.
        OSError: The transcript couldn't be read.
    """
    pending = [d for d in load_deliveries(paths) if d.surface == SESSION and not d.is_fully_acked]
    hook_ids = {d.id for d in pending if d.session_id == session_id}
    tool_ids = {d.id for d in pending if d.session_id is None}
    if transcript is None or not hook_ids | tool_ids:
        return 0
    replies = replies_after_deliveries(transcript, hook_ids, tool_ids)
    bookmark = read_through(paths)
    acked = 0
    for delivery in pending:
        if delivery.id not in replies:
            continue
        through = relayed_through(delivery, replies[delivery.id], bookmark)
        if through is None or through <= (delivery.acked_through or 0):
            continue
        bookmark = ack_delivery(paths, delivery.id, through, now) or bookmark
        acked += 1
    return acked
