"""Which Claude Code permission modes a managed session may run in.

Managed sessions run unattended, so tool calls the CLI would prompt for must
reach the owner's approval dialog. Allowed modes:
- "default": every prompted call asks.
- "acceptEdits": file edits run without asking, and so do the Bash commands
  mkdir, touch, rm, rmdir, mv, cp and sed and the PowerShell cmdlets
  Set-Content, Add-Content, Clear-Content and Remove-Item (and their aliases)
  on paths inside the repo, which can delete or overwrite files. Everything
  else still asks. Choose it only for work where that is fine.
- "plan": read-only planning.
"bypassPermissions" and the other modes that skip or auto-answer every
prompt are refused.
"""

from typing import Final

DEFAULT_PERMISSION_MODE: Final = "default"
ALLOWED_PERMISSION_MODES: Final = ("default", "acceptEdits", "plan")
BYPASS_PERMISSION_MODE: Final = "bypassPermissions"


class PermissionModeError(ValueError):
    """A permission mode a managed session may not use."""


def validate_permission_mode(mode: object) -> str:
    """Check a requested permission mode and return it.

    Args:
        mode: The requested mode; usually a string from IPC or MCP input.

    Returns:
        The mode, unchanged, when it is one of ALLOWED_PERMISSION_MODES.

    Raises:
        PermissionModeError: For bypassPermissions (always refused) or any
            other mode, or a non-string value.
    """
    if mode == BYPASS_PERMISSION_MODE:
        raise PermissionModeError(
            "bypassPermissions is never allowed for managed sessions: every tool call that "
            "needs approval must reach the owner. Use default, acceptEdits or plan."
        )
    if not isinstance(mode, str) or mode not in ALLOWED_PERMISSION_MODES:
        allowed = ", ".join(ALLOWED_PERMISSION_MODES)
        raise PermissionModeError(f"permission_mode must be one of {allowed}; got {mode!r}")
    return mode
