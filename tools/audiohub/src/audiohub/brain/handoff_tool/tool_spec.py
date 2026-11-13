"""What the hand-off tool is called and how it's described to Claude.

The SDK adapter (brain/sdk_tools.py) registers the tool under these names, and
the permission gate always allows it by HAND_OFF_TOOL_NAME.
"""

from audiohub.brain.handoff_tool.message import MAX_JOB_CHARS

# The voice brain's own in-process MCP server. No .mcp.json server uses this name.
HAND_OFF_SERVER = "voice"
HAND_OFF_TOOL = "hand_off_to_main_session"
# The name the CLI gives the tool: "mcp__<server>__<tool>".
HAND_OFF_TOOL_NAME = f"mcp__{HAND_OFF_SERVER}__{HAND_OFF_TOOL}"
# The one input field: the voice agent's summary of the job.
JOB_FIELD = "job"

HAND_OFF_DESCRIPTION = (
    "Pass a job to the owner's main Signal session (the orchestrator), which can change "
    "code and settings and do long or complicated work. Use it for anything you can't "
    "or shouldn't do yourself. It runs straight away, without asking the owner, so "
    "don't ask the owner first; say one short line that you're handing it off. Put the job "
    "in `job` as one or two "
    f"plain sentences (at most {MAX_JOB_CHARS} characters; longer is cut). The owner's own "
    "recent words go with it automatically, so don't repeat them. The result says "
    "whether it was sent."
)
