"""Connect to an Edge that runs elsewhere (a docker job) over CDP, and harden its context.

connect_over_cdp gives the browser's existing default context, which gets the
driver's defaults rather than the local backend's launch options: downloads
are accepted and service workers allowed. So before anything touches a page:
- Browser.setDownloadBehavior "deny" is sent. It is the download control that
  holds: while a CDP client has set allow or allowAndName (the connect itself
  sets allowAndName), Edge ignores its DownloadRestrictions policy.
- Playwright's own service-worker blocker is repeated as an init script,
  because requests a worker serves bypass routing.
The relay token goes in `headers`, which Playwright sends on every connection
(the /json/version fetches and the WebSocket). See refdocs/research/docker-browser.md section 2.
"""

from playwright.async_api import Browser, BrowserContext, Playwright

# The same script Playwright injects for service_workers="block".
SERVICE_WORKER_BLOCKER = (
    "if (self.ServiceWorkerContainer) ServiceWorkerContainer.prototype.register = "
    "async () => { console.warn('Service Worker registration blocked'); };"
)


async def connect_context(
    playwright: Playwright, endpoint: str, headers: dict[str, str]
) -> BrowserContext:
    """Connect over CDP and return the hardened default context.

    Args:
        playwright: The running Playwright instance.
        endpoint: The relay's http:// address on the host's loopback.
        headers: Sent on every connection (the relay token).

    Raises:
        playwright.async_api.Error: If the connection or a hardening step fails;
            the connection is closed first.
    """
    browser = await playwright.chromium.connect_over_cdp(endpoint, headers=headers)
    try:
        context = browser.contexts[0]
        await _harden(browser, context)
    except BaseException:
        await browser.close()
        raise
    return context


async def _harden(browser: Browser, context: BrowserContext) -> None:
    # This CDP session stays attached for the life of the connection.
    session = await browser.new_browser_cdp_session()
    await session.send("Browser.setDownloadBehavior", {"behavior": "deny"})
    await context.add_init_script(SERVICE_WORKER_BLOCKER)
