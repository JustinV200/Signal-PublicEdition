"""Public API of claude_sessions.approvals: who may approve managed sessions' tool calls, and how.

Holds the permission-mode policy (bypassPermissions is refused), the Approver
interface, the describer for tool calls, and the default dialog approver.
"""

from claude_sessions.approvals.approver import ApprovalRequest, Approver
from claude_sessions.approvals.describe import describe_tool_call
from claude_sessions.approvals.dialog_approver import DialogApprover
from claude_sessions.approvals.modes import (
    ALLOWED_PERMISSION_MODES,
    BYPASS_PERMISSION_MODE,
    DEFAULT_PERMISSION_MODE,
    PermissionModeError,
    validate_permission_mode,
)

__all__ = [
    "ALLOWED_PERMISSION_MODES",
    "BYPASS_PERMISSION_MODE",
    "DEFAULT_PERMISSION_MODE",
    "ApprovalRequest",
    "Approver",
    "DialogApprover",
    "PermissionModeError",
    "describe_tool_call",
    "validate_permission_mode",
]
