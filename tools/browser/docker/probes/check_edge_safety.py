"""Phase 0 checks on Edge's own protections in the container, driven over CDP.

Covers the managed-policy path (edge://policy), the sandbox page (part of check
10), the service-worker blocker, downloads (check 7), and the firewall and
--host-resolver-rules as a page sees them (part of check 11).
"""

import json
from pathlib import Path

import docker_job
from playwright.async_api import Browser, BrowserContext, Page
from playwright.async_api import Error as PlaywrightError
from results import Result

POLICY_FILE = Path(__file__).resolve().parent.parent / "guest" / "edge_policy.json"
GUEST_POLICY_PATH = "/etc/opt/edge/policies/managed/signal.json"
DOWNLOAD_DIR = "/home/edge/Downloads"
DOWNLOAD_NAME = "spike-download.txt"
PUBLIC_URL = "https://example.com/"
# Playwright's own blocker, repeated because CDP-connected contexts allow workers.
SERVICE_WORKER_BLOCKER = (
    "if (self.ServiceWorkerContainer) ServiceWorkerContainer.prototype.register = "
    "async () => { console.warn('Service Worker registration blocked'); };"
)
# (policy file, CDP Browser.setDownloadBehavior) -> does the file land?
EXPECTED_DOWNLOADS = {
    ("policy", "deny"): False,
    ("policy", "default"): False,
    # A CDP allow overrides DownloadRestrictions, and Playwright's connect_over_cdp
    # sets allowAndName on the default context, so the CDP deny is the real control.
    ("policy", "allow"): True,
    ("no policy", "deny"): False,
    ("no policy", "default"): True,
    ("no policy", "allow"): True,
}
PAGE_SETTLE_MS = 3000
NAVIGATION_TIMEOUT_MS = 15000
POLICY_RELOAD_TIMEOUT_MS = 30000


async def harden(browser: Browser, context: BrowserContext) -> None:
    """What remote_cdp will do after connecting: deny downloads, block service workers."""
    session = await browser.new_browser_cdp_session()
    await session.send("Browser.setDownloadBehavior", {"behavior": "deny"})
    await context.add_init_script(SERVICE_WORKER_BLOCKER)


async def check_policies(page: Page) -> Result:
    """edge://policy lists every policy from edge_policy.json, so the path is the right one."""
    text = await _page_text(page, "edge://policy")
    names = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    missing = [name for name in names if name not in text]
    has_error = "Error" in text
    detail = f"missing {missing}" if missing else f"all {len(names)} policies listed"
    return Result(
        "policy path (edge://policy)",
        not missing and not has_error,
        detail + f", error shown: {has_error}",
    )


async def check_sandbox_page(page: Page) -> Result:
    """10 (page part): edge://sandbox reports the namespace and seccomp-BPF sandboxes."""
    text = await _page_text(page, "edge://sandbox")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    passed = "adequately sandboxed" in text and "Namespace" in text
    return Result("10 edge://sandbox", passed, "; ".join(lines[:14]))


async def check_service_worker_blocked(page: Page) -> Result:
    """The init script replaces register(), so no worker can be installed."""
    await page.goto(PUBLIC_URL)
    outcome = await page.evaluate(
        "navigator.serviceWorker.register('/sw.js').then(r => String(r), e => 'rejected: ' + e)"
    )
    return Result("service worker blocker", outcome == "undefined", f"register() gave {outcome!r}")


async def check_downloads(browser: Browser, job: docker_job.Job, page: Page) -> Result:
    """7: which (policy, CDP download behavior) pairs let a download land in the guest.

    Passes when every pair matches EXPECTED_DOWNLOADS. "default" hands the
    decision back to Edge, so it shows the policy on its own; the "no policy"
    rows prove the check can see a file land. The policy file is removed from
    this throwaway container half way, and the behavior is left at deny.
    """
    session = await browser.new_browser_cdp_session()
    observed: dict[str, bool] = {}
    for policy_state, behavior in EXPECTED_DOWNLOADS:
        if policy_state == "no policy" and not any(key.startswith("no policy") for key in observed):
            docker_job.docker("exec", job.name, "rm", GUEST_POLICY_PATH)
            await _wait_for_policy_reload(page)
        params = {"behavior": behavior}
        if behavior == "allow":
            params["downloadPath"] = DOWNLOAD_DIR
        await session.send("Browser.setDownloadBehavior", params)
        observed[f"{policy_state} + {behavior}"] = await _try_download(job, page)
    await session.send("Browser.setDownloadBehavior", {"behavior": "deny"})
    expected = {
        f"{state} + {behavior}": landed for (state, behavior), landed in EXPECTED_DOWNLOADS.items()
    }
    return Result("7 downloads denied", observed == expected, f"file landed: {observed}")


async def check_edge_firewall(context: BrowserContext, host_ips: list[str]) -> Result:
    """11 (page part): the host, Docker's host alias and a private IP behind a public name fail."""
    blocked_urls = [
        "http://host.docker.internal:8770/",
        "http://192-168-65-254.sslip.io:8770/",
        *(f"http://{address}:1234/" for address in host_ips),
    ]
    errors = {url: await _navigation_error(context, url) for url in blocked_urls}
    public_error = await _navigation_error(context, PUBLIC_URL)
    passed = public_error is None and all(errors.values())
    detail = f"public load error: {public_error}; {errors}"
    return Result("11 firewall seen from Edge", passed, detail)


async def check_resolver_rules(context: BrowserContext) -> Result:
    """SIGNAL_RESOLVER_RULES reaches Edge as one argv element: example.net is mapped away."""
    error = await _navigation_error(context, "https://example.net/")
    passed = error is not None and "ERR_NAME_NOT_RESOLVED" in error
    return Result("--host-resolver-rules from env", passed, f"example.net: {error}")


async def _page_text(page: Page, url: str) -> str:
    await page.goto(url)
    await page.wait_for_timeout(PAGE_SETTLE_MS)
    return await page.inner_text("body")


async def _try_download(job: docker_job.Job, page: Page) -> bool:
    """Click a download link, then report whether the file landed in the guest."""
    docker_job.docker("exec", "-u", "edge", job.name, "rm", "-rf", DOWNLOAD_DIR)
    # set_content fails on edge:// pages (they require TrustedHTML), so leave them first.
    await page.goto("about:blank")
    await page.set_content(
        f'<a id="d" href="data:text/plain,hello" download="{DOWNLOAD_NAME}">get</a>'
    )
    await page.click("#d")
    await page.wait_for_timeout(PAGE_SETTLE_MS)
    found = docker_job.docker(
        "exec",
        "-u",
        "edge",
        job.name,
        "find",
        "/home/edge",
        "/tmp",
        "-name",
        f"{DOWNLOAD_NAME}*",
        check=False,
    ).stdout
    return bool(found.strip())


async def _wait_for_policy_reload(page: Page) -> None:
    """Reload edge://policy until DownloadRestrictions is gone (Edge watches the folder)."""
    await page.goto("edge://policy")
    await page.wait_for_function(
        "!document.body.innerText.includes('DownloadRestrictions')",
        timeout=POLICY_RELOAD_TIMEOUT_MS,
        polling=1000,
    )


async def _navigation_error(context: BrowserContext, url: str) -> str | None:
    """Load `url` in a fresh tab; return the first error line, or None if it loaded.

    A fresh tab per load matters: the error page commits after goto has already
    raised, and interrupts the next navigation on the same tab.
    """
    tab = await context.new_page()
    try:
        await tab.goto(url, timeout=NAVIGATION_TIMEOUT_MS)
    except PlaywrightError as error:
        return str(error).splitlines()[0]
    finally:
        await tab.close()
    return None
