"""mail_digest.kb: which life/ files a run may edit, and the post-run guard on those edits.

It also has the git check (is_reviewed) that says when a file the guard couldn't
check has been reviewed, so the runner stops flagging it, and the lines a run
added (added_lines), for the digest email.
"""

from mail_digest.kb.expire import expire_notes
from mail_digest.kb.guard import GuardReport, guard_edits
from mail_digest.kb.line_rules import (
    DIGEST_RULES,
    LineRules,
    added_lines,
    edit_problems,
    is_safe_text,
)
from mail_digest.kb.paths import fold_case
from mail_digest.kb.review import is_reviewed
from mail_digest.kb.snapshot import snapshot
from mail_digest.kb.targets import KbTargets, find_plan, find_targets, week_folder_name

__all__ = [
    "DIGEST_RULES",
    "GuardReport",
    "KbTargets",
    "LineRules",
    "added_lines",
    "edit_problems",
    "expire_notes",
    "find_plan",
    "find_targets",
    "fold_case",
    "guard_edits",
    "is_reviewed",
    "is_safe_text",
    "snapshot",
    "week_folder_name",
]
