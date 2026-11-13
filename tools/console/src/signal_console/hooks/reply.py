"""Cut a turn's final message so the hook's POST body fits the server's 64 KB limit.

Measured on the encoded body, because JSON escaping (quotes, newlines,
control characters) and multi-byte characters make its size differ from the
character count. Stdlib only, so the hook starts fast.
"""

import json
from typing import Any

from signal_console.local_api import MAX_BODY_BYTES

CUT_NOTE = "\n\n[cut: the full reply is in the Claude Code session]"


def fit_reply(fields: dict[str, Any], text: str) -> str:
    """The reply, or its longest prefix plus CUT_NOTE, so `fields | {"text": ...}` fits.

    Args:
        fields: The body's other fields (phase, session_id, ...).
        text: The full reply.

    Returns:
        The text to send. A lone surrogate (from a \\ud800-style escape) has
        no UTF-8 form, so it's sent as "?".
    """
    text = text.encode("utf-8", "replace").decode("utf-8")
    if _body_bytes(fields, text) <= MAX_BODY_BYTES:
        return text
    # Each character costs at least one byte, so no longer prefix can fit.
    low, high = 0, min(len(text), MAX_BODY_BYTES)
    while low < high:  # binary search for the longest prefix that fits
        middle = (low + high + 1) // 2
        if _body_bytes(fields, text[:middle] + CUT_NOTE) <= MAX_BODY_BYTES:
            low = middle
        else:
            high = middle - 1
    return text[:low] + CUT_NOTE


def _body_bytes(fields: dict[str, Any], text: str) -> int:
    # Encoded exactly as post_local encodes the body.
    return len(json.dumps(fields | {"text": text}, ensure_ascii=False).encode("utf-8"))
