"""Public API of browser_tool.actions.signin: keeping sign-ins and waiting out Duo.

wait_for_duo waits, read only, for the owner's Duo approval; report_location
says where a tab landed; signed_out_note marks a page with a
visible password field; ensure_not_login_loop refuses a third fill_login on a
site within 10 minutes.
"""

from browser_tool.actions.signin.duo_wait import wait_for_duo
from browser_tool.actions.signin.landing import report_location
from browser_tool.actions.signin.login_note import (
    LOGIN_LOOP_REFUSAL,
    ensure_not_login_loop,
    signed_out_note,
)

__all__ = [
    "LOGIN_LOOP_REFUSAL",
    "ensure_not_login_loop",
    "report_location",
    "signed_out_note",
    "wait_for_duo",
]
