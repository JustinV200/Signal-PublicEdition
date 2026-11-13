"""The Backend protocol: how a BrowserSession gets its browser context, and ends it.

A backend is the one place that knows where Edge runs. Everything else in the
tool (routing, redaction, gates, the Duo watch) works on the Playwright
BrowserContext it returns, so the safety controls are the same for each one.
"""

from pathlib import Path
from typing import Protocol

from playwright.async_api import BrowserContext, Playwright

from browser_tool.policy import GuestBlock, HostPolicy


class BackendError(Exception):
    """A backend can't give the session a browser. The message is ours and safe to show."""


class Backend(Protocol):
    """Opens and ends the browser for a BrowserSession.

    Attributes:
        guest_block: Hosts the browser must never reach, or None when the
            plain policy is enough (the desktop browser). The policy is built with it.
        idle_close_s: End the browser after this many seconds without a tool
            call, or None to keep it open.
        downloads_incoming: Where the browser writes in-flight downloads, or
            None when it refuses every download (docker jobs, or [downloads] off).
    """

    guest_block: GuestBlock | None
    idle_close_s: float | None
    downloads_incoming: Path | None

    @property
    def job_label(self) -> str | None:
        """What owner dialogs and Duo voice notes are prefixed with, e.g. "docker job 1a2b3c"."""
        ...

    async def open_context(self, playwright: Playwright, policy: HostPolicy) -> BrowserContext:
        """Start the browser and return its context, hardened, before any page action.

        Raises:
            BackendError: With a message for the model when the browser can't start.
            playwright.async_api.Error: If Playwright can't launch or connect.
        """
        ...

    async def is_job_stale(self) -> bool:
        """Called before every tool call: True when the open browser must end now."""
        ...

    def close(self) -> None:
        """End the browser this backend started. Never blocks, and a second call does nothing."""
        ...
