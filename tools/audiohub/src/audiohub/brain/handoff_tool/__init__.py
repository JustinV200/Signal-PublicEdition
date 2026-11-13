"""Public API of audiohub.brain.handoff_tool: voice passes a job to the main Signal session.

SDK-free: brain/sdk_tools.py registers the tool with the SDK, and the
permission gate always lets it run, without a spoken question.
"""

from audiohub.brain.handoff_tool.main_session import (
    NO_JOB_RESULT,
    SENT_RESULT,
    UNREACHABLE_RESULT,
    HandOff,
    MainSessionHandoff,
)
from audiohub.brain.handoff_tool.message import MARKER, spoken_job
from audiohub.brain.handoff_tool.tool_spec import (
    HAND_OFF_DESCRIPTION,
    HAND_OFF_SERVER,
    HAND_OFF_TOOL,
    HAND_OFF_TOOL_NAME,
    JOB_FIELD,
)

__all__ = [
    "HAND_OFF_DESCRIPTION",
    "HAND_OFF_SERVER",
    "HAND_OFF_TOOL",
    "HAND_OFF_TOOL_NAME",
    "JOB_FIELD",
    "MARKER",
    "NO_JOB_RESULT",
    "SENT_RESULT",
    "UNREACHABLE_RESULT",
    "HandOff",
    "MainSessionHandoff",
    "spoken_job",
]
