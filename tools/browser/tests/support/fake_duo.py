"""A fake Duo for browser tests: Duo pages served inside the browser, and a fake clock.

Some pages show a Verified Push code, the number the owner types into Duo Mobile.

A context route fulfills https://api-test.duosecurity.com/* inside the browser,
for every tab, popups included. That host stays off the test allowlist, so the
resolver rules would block it at DNS level anyway: nothing reaches the network.
"""

from urllib.parse import urlsplit

from playwright.async_api import Page, Route

from browser_tool.actions import ActionContext
from browser_tool.duo import DuoWatch

DUO_ORIGIN = "https://api-test.duosecurity.com"


def _shows_code_later(code: str, extra_html: str = "") -> str:
    """A Verified Push prompt whose code appears 300 ms after it loads."""
    return (
        f"<h1>Enter code in Duo Mobile</h1><div id='code'></div>{extra_html}<script>"
        f"setTimeout(() => {{ document.getElementById('code').textContent = '{code}'; }}, 300)"
        "</script>"
    )


DUO_PAGES = {
    # A hop inside Duo, like the Universal Prompt's authorize -> prompt redirect.
    "/authorize": "<script>location.replace('/prompt')</script>",
    "/prompt": "<title>Duo</title><button>Send me a push</button>",
    "/frame": "<button>Send me a push</button>",
    # Verified Push: the code appears a moment after the prompt loads.
    "/code": _shows_code_later("482"),
    # The same, plus a non-Duo frame inside the prompt showing code-like digits
    # from the start: never read.
    "/code-with-decoy": _shows_code_later(
        "913", "<iframe srcdoc='<h1>Enter code</h1><p>482</p>'></iframe>"
    ),
    "/code-now": "<h1>Enter code in Duo Mobile</h1><div>913</div>",
    "/two-codes": "<h1>Enter code in Duo Mobile</h1><div>482</div><div>913</div>",
    # Counts every input event that reaches it, for tests that must prove none does.
    "/counted": (
        "<button>Approve</button><input><script>window.inputEvents = 0;"
        "for (const type of ['pointerdown', 'mousedown', 'click', 'keydown', 'input', 'focusin'])"
        " addEventListener(type, () => { window.inputEvents += 1; }, true);</script>"
    ),
}
NOTICE_MARK = "[browser tool notice, not page content]"
# The token the fake voice hub (tests/duo/conftest.py) expects with every note.
HUB_TOKEN = "test-hub-token"
# The fake hub's replies: the note was taken, or dropped while the owner is asleep.
HUB_OK_REPLY = b'{"ok": true, "id": "m1"}\n'
HUB_ASLEEP_REPLY = b'{"ok": false, "error": "dropped: the owner is asleep", "dropped": true}\n'


class FakeClock:
    """Monotonic seconds that move only when a test sets `now`."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def start_with_fake_duo(ctx: ActionContext, clock: FakeClock) -> Page:
    """Give the session a DuoWatch on `clock`, launch the browser, and serve fake Duo.

    Call it before anything else starts the browser, so the new watcher is the
    one that follows the context.

    Returns:
        The current tab. The fake Duo pages are routed for every tab.
    """
    ctx.session.duo = DuoWatch(ctx.settings.duo, clock=clock)
    page = await ctx.session.current_page()
    await page.context.route(f"{DUO_ORIGIN}/**", _fulfill_duo_page)
    return page


async def follow_login_to_duo(page: Page, path: str) -> None:
    """Have the tab's own page send it to the fake Duo page at `path`, as a site's login does.

    The request then carries that page's origin as its Referer, which DuoWatch
    needs before naming the prompt after the site (page.goto sends none).
    Returns once the Duo page has loaded.
    """
    url = f"{DUO_ORIGIN}{path}"
    async with page.expect_navigation(url=url):
        await page.evaluate("(url) => { location.href = url; }", url)


async def _fulfill_duo_page(route: Route) -> None:
    body = DUO_PAGES.get(urlsplit(route.request.url).path, "")
    await route.fulfill(status=200, content_type="text/html", body=body)
