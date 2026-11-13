"""Phase 0 checks 1-6 and 9: do the Playwright APIs tools/browser relies on work over CDP?

Each check runs against `browser.contexts[0]` of a container's Edge, reached with
`connect_over_cdp`, which is what phase 1's remote_cdp backend will use. The
pre-existing about:blank tab is used where it matters, because DuoWatch.watch
attaches to tabs that are already open.
"""

import base64
import re
from urllib.parse import urlsplit

from playwright.async_api import Browser, BrowserContext, Page, Playwright, Request, Route
from playwright.async_api import Error as PlaywrightError
from results import Result

from browser_tool.redaction import SENSITIVE_SELECTOR, sensitive_masks

# A throwaway engine for the registration-order half of check 2.
EARLY_ENGINE = "spike-early"
EARLY_ENGINE_SCRIPT = (
    "({ query: (root, s) => root.querySelector(s),"
    " queryAll: (root, s) => Array.from(root.querySelectorAll(s)) })"
)
PUBLIC_URL = "https://example.com/"
BLOCKED_HOST = "example.org"
REDIRECTING_URL = "https://google.com/"
MASK_RGB = [255, 0, 255]
EVENT_SETTLE_MS = 2000
# Decodes a PNG in the page and reads one pixel, so no image library is needed.
READ_PIXEL_JS = """async ([source, x, y]) => {
  const image = new Image();
  image.src = source;
  await image.decode();
  const canvas = document.createElement('canvas');
  canvas.width = image.width;
  canvas.height = image.height;
  const context = canvas.getContext('2d');
  context.drawImage(image, 0, 0);
  return Array.from(context.getImageData(x, y, 1, 1).data);
}"""


def check_about_blank(browser: Browser) -> Result:
    """9: one default context with exactly one about:blank tab right after connecting."""
    contexts = browser.contexts
    urls = [page.url for page in contexts[0].pages] if contexts else []
    passed = len(contexts) == 1 and urls == ["about:blank"]
    return Result("9 about:blank start", passed, f"{len(contexts)} context(s), tabs {urls}")


async def check_routing(context: BrowserContext) -> Result:
    """1: context.route and the request listener, on the old tab and on a new one."""
    routed: list[str] = []
    hops: list[str] = []

    async def guard(route: Route) -> None:
        routed.append(route.request.url)
        if urlsplit(route.request.url).hostname == BLOCKED_HOST:
            await route.abort("blockedbyclient")
        else:
            await route.continue_()

    def note_hop(request: Request) -> None:
        if request.redirected_from is not None:
            hops.append(request.url)

    await context.route("**/*", guard)
    context.on("request", note_hop)
    old_tab = context.pages[0]
    new_tab = await context.new_page()
    try:
        await old_tab.goto(PUBLIC_URL)
        blocked = [await _is_blocked(tab, f"https://{BLOCKED_HOST}/") for tab in (old_tab, new_tab)]
        await old_tab.goto(REDIRECTING_URL)
    finally:
        await new_tab.close()
        await context.unroute("**/*", guard)
    saw_public = any(url.startswith(PUBLIC_URL) for url in routed)
    passed = saw_public and all(blocked) and bool(hops)
    detail = (
        f"routed {len(routed)} requests, blocked on old/new tab {blocked}, redirect hops {hops[:2]}"
    )
    return Result("1 route + request listener", passed, detail)


async def register_early_engine(playwright: Playwright) -> None:
    """Register EARLY_ENGINE before connecting, the order BrowserSession uses today."""
    await playwright.selectors.register(EARLY_ENGINE, EARLY_ENGINE_SCRIPT)


async def check_selector_engine(page: Page) -> Result:
    """2: which selector engines reach a CDP-connected default context.

    EARLY_ENGINE was registered before connect_over_cdp, signal-sensitive after.
    The Python client sends engines only in a new context's creation params, or
    later to contexts it already tracks, so only the late one is expected to work.
    """
    await page.set_content(
        '<input type="password" value="hunter2"><input name="otp"><input name="city">'
    )
    try:
        early = str(await page.locator(f"{EARLY_ENGINE}=input").count())
    except PlaywrightError as error:
        early = str(error).splitlines()[0].split(": ", 1)[-1]
    count = await page.locator(SENSITIVE_SELECTOR).count()
    detail = f"registered after connect: matched {count} of 3 (want 2); before connect: {early}"
    return Result("2 selector engine", count == 2, detail)


async def check_aria_refs(page: Page) -> Result:
    """3: aria_snapshot(mode="ai") gives refs, and get_by_ref clicks the right element."""
    await page.set_content("<button onclick=\"document.title='clicked'\">Press me</button>")
    snapshot = await page.aria_snapshot(mode="ai")
    match = re.search(r'button "Press me" \[ref=(\w+)\]', snapshot)
    if match is None:
        return Result("3 aria refs + get_by_ref", False, f"no ref in snapshot: {snapshot[:200]!r}")
    await page.get_by_ref(match.group(1)).click()
    title = await page.title()
    return Result(
        "3 aria refs + get_by_ref", title == "clicked", f"ref {match.group(1)}, title {title!r}"
    )


async def check_handles_and_frames(page: Page) -> Result:
    """4: ElementHandle.fill and owner_frame() inside an iframe, and frame URLs."""
    await page.set_content('<iframe srcdoc="<input id=field>"></iframe>')
    await page.wait_for_function(
        "document.querySelector('iframe').contentDocument?.getElementById('field')"
    )
    child = next(frame for frame in page.frames if frame != page.main_frame)
    handle = await child.locator("#field").element_handle()
    owner = await handle.owner_frame()
    await handle.fill("filled-by-handle")
    value = await child.locator("#field").input_value()
    urls = [frame.url for frame in page.frames]
    passed = owner == child and value == "filled-by-handle" and child.url == "about:srcdoc"
    return Result(
        "4 ElementHandle.fill, owner_frame, frame URLs", passed, f"value {value!r}, frames {urls}"
    )


async def check_masked_screenshot(page: Page) -> Result:
    """5: screenshot(mask=sensitive_masks(page)) paints the password field magenta."""
    await page.set_content(
        '<input id="secret" type="password" value="hunter2" style="width:300px">'
    )
    png = await page.screenshot(mask=sensitive_masks(page), animations="disabled")
    box = await page.locator("#secret").bounding_box()
    x, y = int(box["x"] + box["width"] / 2), int(box["y"] + box["height"] / 2)
    source = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    pixel = await page.evaluate(READ_PIXEL_JS, [source, x, y])
    passed = pixel[:3] == MASK_RGB
    return Result("5 screenshot(mask=...)", passed, f"{len(png)} byte PNG, field pixel {pixel}")


async def check_frame_and_popup_events(context: BrowserContext, page: Page) -> Result:
    """6: framenavigated, framedetached and popup on a pre-existing tab, plus context 'page'."""
    events: list[str] = []
    page.on("framenavigated", lambda frame: frame != page.main_frame and events.append("navigated"))
    page.on("framedetached", lambda _frame: events.append("detached"))
    page.on("popup", lambda _popup: events.append("popup"))
    context.on("page", lambda _page: events.append("context page"))
    await page.set_content(
        "<iframe id=f></iframe><button id=o onclick=\"window.open('about:blank')\">open</button>"
    )
    await page.evaluate(f"document.getElementById('f').src = '{PUBLIC_URL}'")
    await page.wait_for_timeout(EVENT_SETTLE_MS)
    await page.evaluate("document.getElementById('f').remove()")
    async with page.expect_popup() as popup_info:
        await page.click("#o")
    await (await popup_info.value).close()
    wanted = {"navigated", "detached", "popup", "context page"}
    passed = wanted <= set(events)
    return Result("6 frame + popup events", passed, f"events seen {sorted(set(events))}")


async def _is_blocked(page: Page, url: str) -> bool:
    try:
        await page.goto(url)
    except PlaywrightError as error:
        return "ERR_BLOCKED_BY_CLIENT" in str(error)
    return False
