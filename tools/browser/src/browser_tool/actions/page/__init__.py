"""Public API of browser_tool.actions.page: the tools that read the current page.

snapshot (snapshot.py) returns one page of the redacted aria snapshot, or of
one ref's subtree, from the tab's cache; find (find.py) searches that cached
text; wait_for (wait_for.py) waits, read only, for text, a ref to go, a URL or
network idle; screenshot (screenshot.py) saves a masked PNG. Pure paging and
search helpers are in paging.py.
"""

from browser_tool.actions.page.find import find
from browser_tool.actions.page.screenshot import screenshot
from browser_tool.actions.page.snapshot import snapshot
from browser_tool.actions.page.wait_for import wait_for

__all__ = ["find", "screenshot", "snapshot", "wait_for"]
