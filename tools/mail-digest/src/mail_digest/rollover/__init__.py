"""mail_digest.rollover: starts each new week in life/ by code, with no model involved.

The digest and the assignment checker call roll_over before they read the week
(through steps.roll_week), and `mail-digest rollover` runs it by hand
(digest/rollover_cli.py).
"""

from mail_digest.rollover.roll import BETWEEN_TERMS, RolloverResult, describe, roll_over
from mail_digest.rollover.templates import TemplateError

__all__ = ["BETWEEN_TERMS", "RolloverResult", "TemplateError", "describe", "roll_over"]
