"""Submitting user-bound text to the kernel, and the source names the loop uses.

Everything the conversation wants the user to hear (Claude's replies, its
background messages, the hub's own error notices) goes through the kernel,
so the dispatcher decides order and timing. This module builds those messages.
"""

from collections.abc import Callable

from audiohub.kernel import OutboundMessage, Priority, create_message

# Claude's direct replies. A "Claude, stop"
# skips every unspoken message from this source.
CLAUDE_SOURCE = "claude"
# Text Claude produces outside a turn, e.g. when a background agent finishes.
BACKGROUND_SOURCE = "claude-background"
# The hub itself, e.g. "I couldn't reach Claude".
HUB_SOURCE = "audiohub"

KernelSubmit = Callable[[OutboundMessage], None]
"""`Kernel.submit`, or a stand-in in tests."""


def submit_text(
    submit: KernelSubmit, source: str, text: str, priority: Priority
) -> OutboundMessage | None:
    """Submit text for the user unless it is blank.

    Args:
        submit: Where the message goes (normally `Kernel.submit`).
        source: Who it is from, e.g. CLAUDE_SOURCE.
        text: What to say, as written (the voice output cleans it later).
        priority: "urgent", "high", "normal" or "low".

    Returns:
        The submitted message, or None if the text was blank and nothing was sent.
    """
    if not text.strip():
        return None
    message = create_message(source, text, priority)
    submit(message)
    return message


def submit_direct_reply(submit: KernelSubmit, text: str) -> OutboundMessage | None:
    """Submit one ReplyText of the current turn: Claude's direct answer to the user.

    It goes out from CLAUDE_SOURCE at high priority, marked `is_direct_reply`
    so the kernel can speak a lone short answer at once without asking Sonnet.

    Args:
        submit: Where the message goes (normally `Kernel.submit`).
        text: The reply text as Claude wrote it.

    Returns:
        The submitted message, or None if the text was blank and nothing was sent.
    """
    if not text.strip():
        return None
    message = create_message(CLAUDE_SOURCE, text, "high", is_direct_reply=True)
    submit(message)
    return message
