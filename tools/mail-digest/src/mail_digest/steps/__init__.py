"""mail_digest.steps: the run steps every runner that edits life/ shares.

The mail digest (digest/) and the assignment checker (assignment_check/) both start
in the background the same way, run claude under the same KB guard, speak their
announcements once through the same state, roll life/ over to the new week
first, and refresh the whiteboard's TODO view.
"""

from mail_digest.steps.background import background_command, start_background_run
from mail_digest.steps.guarded_edit import EditJob, GuardedEdit, run_guarded_edit
from mail_digest.steps.logs import setup_logging
from mail_digest.steps.notices import (
    email_alert,
    failure_alert,
    gap_notices,
    kb_alerts,
    signin_reminders,
)
from mail_digest.steps.outcome import STATE_UNUSABLE, announce_once, record_crash
from mail_digest.steps.rollover import WeekRoll, roll_week
from mail_digest.steps.todo_board import refresh_todo_board

__all__ = [
    "STATE_UNUSABLE",
    "WeekRoll",
    "EditJob",
    "GuardedEdit",
    "announce_once",
    "background_command",
    "email_alert",
    "failure_alert",
    "gap_notices",
    "kb_alerts",
    "record_crash",
    "refresh_todo_board",
    "roll_week",
    "run_guarded_edit",
    "setup_logging",
    "signin_reminders",
    "start_background_run",
]
