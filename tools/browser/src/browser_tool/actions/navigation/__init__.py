"""Public API of browser_tool.actions.navigation: where the tab is and which tab is current.

navigate loads pages (navigate.py); back, forward and reload step through
history, holding back a form resubmission for the send rule (history.py);
tabs, switch_tab, new_tab and close_tab manage tabs (tabs.py). NavigationWatch
(nav_watch.py) notices a main-frame navigation during an action and waits for
it to land; the pointer and key tools use it too.
"""

from browser_tool.actions.navigation.history import back, forward, reload
from browser_tool.actions.navigation.nav_watch import (
    KEY_START_GRACE_S,
    NavigationWatch,
    settle_max_s,
)
from browser_tool.actions.navigation.navigate import navigate
from browser_tool.actions.navigation.tabs import close_tab, list_tabs, new_tab, switch_tab

__all__ = [
    "KEY_START_GRACE_S",
    "NavigationWatch",
    "back",
    "close_tab",
    "forward",
    "list_tabs",
    "navigate",
    "new_tab",
    "reload",
    "settle_max_s",
    "switch_tab",
]
