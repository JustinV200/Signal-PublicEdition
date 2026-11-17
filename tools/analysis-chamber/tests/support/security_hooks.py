"""Helpers for the security hook tests: SDK-shaped hook inputs and deny checks."""


def hook_input(tool_name: str, **tool_input: object) -> dict:
    """A PreToolUse hook input as the SDK sends it, under bypassPermissions."""
    return {
        "hook_event_name": "PreToolUse",
        "session_id": "s",
        "transcript_path": "t",
        "cwd": ".",
        "permission_mode": "bypassPermissions",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_use_id": "u",
    }


def is_deny(output: dict) -> bool:
    """Whether a hook output denies the call."""
    return output.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
