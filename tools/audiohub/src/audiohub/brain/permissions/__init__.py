"""Public API of audiohub.brain.permissions: which of Claude's tool calls voice may run.

The rest of the brain imports from here only.
"""

from audiohub.brain.permissions.gate import (
    PermissionDecider,
    PermissionDecision,
    PermissionGate,
    PermissionRequest,
    is_auto_allowed,
)
from audiohub.brain.permissions.secret_paths import SECRET_READ_DENY_RULES

__all__ = [
    "SECRET_READ_DENY_RULES",
    "PermissionDecider",
    "PermissionDecision",
    "PermissionGate",
    "PermissionRequest",
    "is_auto_allowed",
]
