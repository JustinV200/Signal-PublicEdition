"""Run one action for an MCP tool call: serialize, map errors, scrub the result.

Every tool goes through ToolRunner.run, which guarantees:
- one action at a time (no click racing a snapshot);
- before each action, a backend job that must end (docker: the host has a new
  address) is closed, so the action starts a fresh one; after each, the idle
  timer restarts (docker: the job ends after [browser] idle_close_min quiet);
- no raw exception text in results or logs (Playwright call logs can contain
  fill("<value>")); errors become our own short messages, and logs get the
  exception type plus stack frames, never the message;
- an action stuck on a page dialog it didn't act for (a confirm opened by a
  hover, or by a page timer during wait_for) is cancelled and refused
  (session.run_unless_dialog), instead of hanging on the frozen tab;
- every result, success or error, ends with notes on downloads that finished
  (actions.download_notes; only the call's own downloads are waited for), and
  on alerts, file pickers and open dialogs (actions.dialog_notes), added
  before the scrub since they hold page-supplied file names and messages;
- before the text leaves the process, for every open tab, the live values of all
  secret fields are replaced and the vault's scrub(page, text) is applied
  (actions.scrub_secrets, shared with the snapshot cache); if either fails
  the text is withheld (after a successful action, with
  SCRUB_FAILED_AFTER_ACTION so the model doesn't redo it);
- the first result after a tab enters a Duo prompt, success or error (a withheld
  one included), ends with the Duo watcher's notice (browser_tool.duo), outside
  any page-content wrapper. Notices are appended after the scrub, so a scrub
  failure can't swallow them; they hold only fixed text, a tab index, a
  hostname of only [a-z0-9.-] (else "a login", see browser_tool.duo) or the
  owner's [duo] site_names name for it, a fixed voice ping line and, on
  [duo] code_relay_sites, Duo's verification code as 3-6 ASCII digits; never
  other page text, markup or field values. A site picks its own hostname, so
  the name itself can still spell words.
"""

import asyncio
import logging
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from playwright.async_api import Error as PlaywrightError

from browser_tool.actions import (
    ActionContext,
    ActionError,
    TabReadError,
    describe_playwright_error,
    dialog_notes,
    download_notes,
    scrub_secrets,
)
from browser_tool.backends import BackendError
from browser_tool.server.idle_close import IdleClose
from browser_tool.session import run_unless_dialog

logger = logging.getLogger(__name__)

INTERNAL_ERROR = "internal error in the browser tool (details are in its log)"
SCRUB_FAILED = "error: result withheld because secret scrubbing failed"
# After a successful action, so the model doesn't repeat a send or purchase.
SCRUB_FAILED_AFTER_ACTION = (
    "the action ran; its result was withheld because secret scrubbing failed. "
    "Do not repeat it; take a snapshot() to see the page"
)
# Added when one tab couldn't be read (a frame that never answers, such as a PDF viewer).
TAB_READ_HINT = "; tab {index} could not be read: close_tab({index}) if it stays stuck"

Action = Callable[..., Awaitable[str]]


class ToolRunner:
    """Executes actions on behalf of the MCP tools."""

    def __init__(self, ctx: ActionContext):
        """Args: ctx: The shared action context."""
        self._ctx = ctx
        self._one_at_a_time = asyncio.Lock()
        self._idle_close = IdleClose(
            ctx.session.idle_close_s, self._one_at_a_time, ctx.session.close
        )

    async def run(self, tool_name: str, action: Action, *args: Any) -> str:
        """Run `action(ctx, *args)` and return its scrubbed text.

        Raises:
            ToolError: With a safe, scrubbed message when the action fails or is refused.
        """
        async with self._one_at_a_time:
            self._idle_close.cancel()
            try:
                downloads_before = self._ctx.session.downloads.started
                text, is_failure = await self._invoke(tool_name, action, args)
                notes = await download_notes(self._ctx, downloads_before)
                notes += dialog_notes(self._ctx)
                text = _with_notices(text, notes)
                text, is_scrubbed = await self._scrub(text, is_failure)
                text = _with_notices(text, await self._ctx.session.duo.take_notices())
            finally:
                self._idle_close.arm()
        if is_failure or not is_scrubbed:
            raise ToolError(text)
        return text

    async def _invoke(
        self, tool_name: str, action: Action, args: tuple[Any, ...]
    ) -> tuple[str, bool]:
        try:
            session = self._ctx.session
            await session.end_stale_job()
            work = action(self._ctx, *args)
            return await run_unless_dialog(
                session.dialogs, work, session.current_or_none, tool_name
            ), False
        except (ActionError, BackendError) as error:
            # Both carry messages we wrote ourselves.
            return str(error), True
        except PlaywrightError as error:
            logger.warning("%s failed: %s", tool_name, type(error).__name__)
            return describe_playwright_error(error), True
        except Exception as error:  # noqa: BLE001 - must not reach the SDK, which logs messages
            logger.error("%s crashed: %s\n%s", tool_name, type(error).__name__, _frames_only(error))
            return INTERNAL_ERROR, True

    async def _scrub(self, text: str, is_failure: bool) -> tuple[str, bool]:
        try:
            [text] = await scrub_secrets(self._ctx, [text])
        except Exception as error:  # noqa: BLE001 - fail closed: withhold the text
            logger.error("scrub failed: %s", type(error).__name__)
            withheld = SCRUB_FAILED if is_failure else SCRUB_FAILED_AFTER_ACTION
            if isinstance(error, TabReadError):
                withheld += TAB_READ_HINT.format(index=error.tab_index)
            return withheld, False
        return text, True


def _with_notices(text: str, notices: list[str]) -> str:
    """Append tool-written notices (e.g. a new Duo prompt) after the action's text."""
    return "\n\n".join([text, *notices])


def _frames_only(error: BaseException) -> str:
    """The traceback's file/line/code frames, without the exception message."""
    return "".join(traceback.format_tb(error.__traceback__))
