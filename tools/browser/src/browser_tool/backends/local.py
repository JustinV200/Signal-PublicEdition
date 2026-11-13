"""The local backend: the persistent Edge profile on this desktop, the default.

What is deliberately NOT here: HAR recording, video recording and tracing. All
three would capture what gets typed into pages, including vault-filled secrets.
"""

import logging
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Playwright

from browser_tool.backends.profile_prefs import disable_password_saving
from browser_tool.config import BrowserSettings, Settings, resolve_tool_path
from browser_tool.downloads import INCOMING_FOLDER_NAME, clear_folder
from browser_tool.policy import GuestBlock, HostPolicy, build_resolver_args

logger = logging.getLogger(__name__)

NO_PROXY_FLAG = "--no-proxy-server"


class LocalBackend:
    """Launches the desktop Edge with the dedicated profile; nothing to end but the context."""

    guest_block: GuestBlock | None = None
    idle_close_s: float | None = None

    def __init__(self, settings: Settings):
        """Args: settings: The profile and launch options ([browser]) and [downloads]."""
        self._settings = settings
        self.downloads_incoming = incoming_folder(settings)

    @property
    def job_label(self) -> str | None:
        """The desktop browser has no job, so dialogs and voice notes get no prefix."""
        return None

    async def open_context(self, playwright: Playwright, policy: HostPolicy) -> BrowserContext:
        """See launch_context."""
        return await launch_context(playwright, self._settings, policy)

    async def is_job_stale(self) -> bool:
        """The desktop browser stays open until the owner or the server closes it."""
        return False

    def close(self) -> None:
        """Nothing to do: closing the context closes this Edge."""


def incoming_folder(settings: Settings) -> Path | None:
    """Where Edge writes in-flight downloads: inside the profile, or None when they're off.

    Inside the profile, because only one Edge can open a profile, so the size
    cap's view of the folder is never another browser's downloads.
    """
    if not settings.downloads.enabled:
        return None
    return resolve_tool_path(settings.browser.profile_dir) / INCOMING_FOLDER_NAME


def build_launch_options(
    browser: BrowserSettings, extra_args: list[str], downloads_path: Path | None = None
) -> dict[str, Any]:
    """Keyword options for chromium.launch_persistent_context (minus user_data_dir).

    Args:
        browser: Browser settings (channel, headless, use_system_proxy).
        extra_args: Extra command-line flags, e.g. --host-resolver-rules.
        downloads_path: Accept downloads into this folder, or None to refuse them.

    Returns:
        The options dict, with Chromium's sandbox always enabled.
    """
    # Behind a proxy the proxy resolves hosts, so --host-resolver-rules wouldn't stop
    # redirect hops; go direct unless the owner opts in.
    proxy_args = [] if browser.use_system_proxy else [NO_PROXY_FLAG]
    return {
        "channel": browser.channel,
        "headless": browser.headless,
        "args": [*extra_args, *proxy_args],
        # Playwright passes --no-sandbox unless this is True; keep Edge's sandbox on.
        "chromium_sandbox": True,
        # Requests served by a service worker bypass routing, so block them.
        "service_workers": "block",
        # Accepted downloads land here; browser_tool.downloads moves them out.
        "accept_downloads": downloads_path is not None,
        **({"downloads_path": str(downloads_path)} if downloads_path is not None else {}),
    }


async def launch_context(
    playwright: Playwright, settings: Settings, policy: HostPolicy
) -> BrowserContext:
    """Prepare the profile and launch the persistent browser context.

    Raises:
        ValueError: If the profile's Preferences file is corrupt.
        playwright.async_api.Error: If the browser can't start (for example the
            profile is already open in another browser instance).
    """
    profile_dir = resolve_tool_path(settings.browser.profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    disable_password_saving(profile_dir)
    incoming = incoming_folder(settings)
    if incoming is not None:
        clear_folder(incoming)
    options = build_launch_options(settings.browser, build_resolver_args(policy), incoming)
    logger.info(
        "launching %s (headless=%s) with profile %s",
        settings.browser.channel,
        settings.browser.headless,
        profile_dir,
    )
    return await playwright.chromium.launch_persistent_context(str(profile_dir), **options)
