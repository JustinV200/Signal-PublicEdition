"""Public API of browser_tool.duo: spotting Duo two-factor prompts, which only the owner answers.

DuoWatch follows every tab and, once per prompt, speaks a heads-up through the
audiohub hub and queues a notice for the model, then (on [duo] code_relay_sites
only) reads Duo's Verified Push code and relays it once; DuoWatch.is_in_duo is
the live check behind the acting tools' lockout. wait_until_off_duo waits,
read only, for a tab to leave Duo (wait_for_duo and visit mode's login wait).
"""

from browser_tool.duo.hosts import is_duo_url
from browser_tool.duo.messages import (
    DUO_LOCKOUT_MESSAGE,
    code_note,
    heads_up_note,
    model_notice,
    ping_line,
    shown_site,
)
from browser_tool.duo.pings import PingOutcome, PingSkip
from browser_tool.duo.prompt_state import TabDuoState
from browser_tool.duo.wait import WaitOutcome, wait_for_settle, wait_until_off_duo
from browser_tool.duo.watcher import DuoWatch

__all__ = [
    "DUO_LOCKOUT_MESSAGE",
    "DuoWatch",
    "PingOutcome",
    "PingSkip",
    "TabDuoState",
    "WaitOutcome",
    "code_note",
    "heads_up_note",
    "is_duo_url",
    "model_notice",
    "ping_line",
    "shown_site",
    "wait_for_settle",
    "wait_until_off_duo",
]
