"""Turn PDF document responses into downloads, so tabs don't show Edge's PDF viewer.

Edge ignores the plugins.always_open_pdf_externally pref under Playwright, and
its viewer is a frame tools can't read (reading it never returns). So each tab
gets a CDP session with the Fetch domain paused at the response stage, for
document loads only (the main frame, same-process iframes, popups): a response whose
Content-Type is a PDF goes on with "Content-Disposition: attachment" added, and
the browser saves it as a download instead. It then takes the usual path
through browser_tool.downloads (policy check, size cap, safe name) and the
download notes, and read_download reads it. Every other response goes on
untouched. The request itself is untouched too: it already went through the
request guard's routing and the DNS block, and is fetched only once, by Edge.

Known gaps: a popup's very first load can start before its session attaches,
so a PDF opened straight into a new tab may still show the viewer. A
cross-origin iframe that runs out of process has its own CDP target, which
this page session may not intercept, so a PDF there may show the viewer too.
The result scrub's per-frame timeout (redaction.value_scrub) keeps either from
freezing the tools.
"""

import asyncio
import logging
from typing import Any

from playwright.async_api import BrowserContext, CDPSession, Page
from playwright.async_api import Error as PlaywrightError

logger = logging.getLogger(__name__)

PDF_CONTENT_TYPES = ("application/pdf", "application/x-pdf")
ATTACHMENT_HEADER = {"name": "Content-Disposition", "value": "attachment"}
DOCUMENT_RESPONSES = {"patterns": [{"resourceType": "Document", "requestStage": "Response"}]}


class PdfDownloads:
    """Attaches the PDF-to-download rule to every open and future tab of a context."""

    def __init__(self) -> None:
        """Start with no tabs attached; in-flight attach and answer tasks are kept here."""
        self._tasks: set[asyncio.Task[None]] = set()

    async def watch(self, context: BrowserContext) -> None:
        """Attach to the context's open tabs now, and to each new tab as it opens."""
        for page in context.pages:
            await self._attach(context, page)
        context.on("page", lambda page: self._spawn(self._attach(context, page)))

    async def _attach(self, context: BrowserContext, page: Page) -> None:
        """Pause `page`'s document responses on a new CDP session (a closed tab is skipped)."""
        try:
            session = await context.new_cdp_session(page)
            session.on("Fetch.requestPaused", lambda event: self._spawn(_answer(session, event)))
            await session.send("Fetch.enable", DOCUMENT_RESPONSES)
        except PlaywrightError as error:
            logger.debug("PDF rule not attached to a tab: %s", type(error).__name__)

    def _spawn(self, work: Any) -> None:
        """Run `work` in the background, keeping a reference until it ends."""
        task = asyncio.ensure_future(work)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


def is_pdf_response(headers: list[dict[str, str]]) -> bool:
    """True when the response headers say the body is a PDF (any case, any parameters)."""
    for header in headers:
        if header.get("name", "").lower() == "content-type":
            media_type = header.get("value", "").split(";")[0].strip().lower()
            return media_type in PDF_CONTENT_TYPES
    return False


async def _answer(session: CDPSession, event: dict[str, Any]) -> None:
    """Let one paused document response go on: as a download when it is a PDF.

    A paused response that is never answered would hang its load, so every
    path answers it; an error (the tab closed meanwhile) is logged by type only.
    """
    headers = event.get("responseHeaders") or []
    answer: dict[str, Any] = {"requestId": event["requestId"]}
    # A load that failed has no response to go on with; it goes on as a request, and fails.
    method = "Fetch.continueRequest" if "responseErrorReason" in event else "Fetch.continueResponse"
    if method == "Fetch.continueResponse" and is_pdf_response(headers):
        kept = [header for header in headers if header["name"].lower() != "content-disposition"]
        answer["responseCode"] = event.get("responseStatusCode", 200)
        answer["responseHeaders"] = [*kept, ATTACHMENT_HEADER]
        logger.info("a PDF response is saved as a download instead of shown")
    try:
        await session.send(method, answer)
    except PlaywrightError as error:
        logger.debug("paused response not continued: %s", type(error).__name__)
