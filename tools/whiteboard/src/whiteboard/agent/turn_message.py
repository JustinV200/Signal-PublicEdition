"""Builds the SDK user message for one board-changed turn: the snapshot image plus text.

claude-agent-sdk 0.2.168's ClaudeSDKClient.query() takes an async iterable of
raw stream-json message dicts and writes them to the CLI unchanged, so the
message content can be a list of Anthropic content blocks, including a base64
`image` block. The PNG path is in the text too, as a fallback the agent can Read.
"""

import base64
import struct
from collections.abc import Mapping, Sequence
from typing import Any

from whiteboard.agent.board_change import BoardChange
from whiteboard.agent.prompt import build_turn_text

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# The IHDR chunk always comes first: width and height are big-endian uint32s
# at bytes 16-24 of the file.
PNG_SIZE_OFFSET = 16
PNG_SIZE_END = 24


def build_user_message(change: BoardChange, items: Sequence[Mapping]) -> dict[str, Any]:
    """Build the stream-json user message for one turn.

    Args:
        change: The (possibly coalesced) board change.
        items: The scene items currently projected.

    Returns:
        A {"type": "user", "message": {...}} dict ready for ClaudeSDKClient.query().

    Raises:
        OSError: The snapshot can't be read.
        ValueError: The snapshot isn't a PNG.
    """
    png = change.png_path.read_bytes()
    text = build_turn_text(str(change.png_path), png_size(png), change.changed_bbox, items)
    return user_message(png, text)


def user_message(png: bytes, text: str) -> dict[str, Any]:
    """Wrap a PNG (as a base64 image block) and a text block as a stream-json user message."""
    return stream_message([image_block(png), {"type": "text", "text": text}])


def image_block(png: bytes) -> dict[str, Any]:
    """A base64 PNG as an Anthropic image content block."""
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.b64encode(png).decode("ascii"),
        },
    }


def stream_message(content: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap content blocks as a stream-json user message."""
    return {
        "type": "user",
        "message": {"role": "user", "content": content},
        "parent_tool_use_id": None,
    }


def png_size(png: bytes) -> tuple[int, int]:
    """Read (width, height) from a PNG's header.

    Raises:
        ValueError: The bytes aren't a PNG.
    """
    if not png.startswith(PNG_SIGNATURE) or len(png) < PNG_SIZE_END:
        raise ValueError("snapshot is not a PNG file")
    width, height = struct.unpack(">II", png[PNG_SIZE_OFFSET:PNG_SIZE_END])
    return width, height
