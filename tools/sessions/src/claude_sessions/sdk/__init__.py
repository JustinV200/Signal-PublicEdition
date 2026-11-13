"""Public API of claude_sessions.sdk: the thin adapter over claude-agent-sdk's client.

Only this package (and repos' transcript listing) imports claude_agent_sdk, so
the daemon's session logic works with plain events and a fakeable client.
"""

from claude_sessions.sdk.client import ClientFactory, SessionClient, create_sdk_client
from claude_sessions.sdk.events import AssistantText, SessionEvent, SessionIdentified, TurnEnded
from claude_sessions.sdk.options import SETTING_SOURCES, LaunchSpec, SessionOptions, build_options
from claude_sessions.sdk.permissions import (
    DENIED_MESSAGE,
    ToolCall,
    ToolCallDecider,
    make_can_use_tool,
)
from claude_sessions.sdk.translate import translate_message

__all__ = [
    "DENIED_MESSAGE",
    "SETTING_SOURCES",
    "AssistantText",
    "ClientFactory",
    "LaunchSpec",
    "SessionClient",
    "SessionEvent",
    "SessionIdentified",
    "SessionOptions",
    "ToolCall",
    "ToolCallDecider",
    "TurnEnded",
    "build_options",
    "create_sdk_client",
    "make_can_use_tool",
    "translate_message",
]
