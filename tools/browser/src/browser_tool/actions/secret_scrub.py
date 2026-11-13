"""scrub_secrets: remove every open tab's live secret values and vault fills from texts.

The one scrub used both by the tool runner (every result, before it leaves the
process) and, through scrub_or_refuse, by the read tools (before a snapshot is
cached, and on the URL wait_for matches), so find and wait_for can't be used as
a yes/no oracle on a secret mirrored into page text or the URL.
The live values of all secret fields are read from all tabs together (a value
filled in one tab can show up in another) and replaced, then the vault's
scrub(page, text) runs for each tab. A tab frozen by a dialog can't be read
(its evaluate would never return), so for it the values last read from it are
used (ctx.secret_values, refreshed by every scrub). Known gap: a value typed
into that tab after its last read and before the dialog opened isn't known.

URLs shown to the model go through shown_url: origin and path, scrubbed, then
percent-decoded (so a secret Edge encoded as my%20pw is still found, with
control characters such as a decoded %0A replaced) and scrubbed again.
"""

import asyncio
import logging
from urllib.parse import unquote

from playwright.async_api import Page

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.policy import display_url, origin_of
from browser_tool.redaction import live_secret_values, replace_unsafe_chars, replace_values
from browser_tool.session import read_until_dialog

logger = logging.getLogger(__name__)

SCRUB_REFUSAL = "blocked: could not scrub secrets from this page's text"
# Stands in for a control or format character in a decoded URL path.
UNSAFE_URL_CHAR = "_"


class TabReadError(Exception):
    """Reading one tab's secret values failed (or timed out), so the scrub must fail closed.

    Attributes:
        tab_index: The tab's index in tabs(), so the model can close it.
    """

    def __init__(self, tab_index: int) -> None:
        """Args: tab_index: The failing tab's index."""
        super().__init__(f"reading tab {tab_index} failed")
        self.tab_index = tab_index


async def scrub_secrets(ctx: ActionContext, texts: list[str]) -> list[str]:
    """Return `texts`, each with every open tab's secrets removed.

    Args:
        ctx: The action context (its session's tabs and its vault filler).
        texts: The texts to scrub; the values are read once for all of them.

    Raises:
        TabReadError: If reading one tab's values failed or timed out.
        Exception: Whatever the vault's scrub raised.
            Callers must fail closed: withhold the text, never use it unscrubbed.
    """
    pages = ctx.session.pages()
    found = await asyncio.gather(
        *(_tab_values(ctx, page, index) for index, page in enumerate(pages))
    )
    values = set().union(*found)
    scrubbed = []
    for text in texts:
        text = replace_values(text, values)
        for page in pages:
            text = ctx.filler.scrub(page, text)
        scrubbed.append(text)
    return scrubbed


async def _tab_values(ctx: ActionContext, page: Page, index: int) -> set[str]:
    """`page`'s live secret values, or the last ones read if a dialog freezes it.

    Raises:
        TabReadError: If reading them raised or timed out (callers fail closed).
    """
    try:
        is_read, values = await read_until_dialog(
            ctx.session.dialogs, page, lambda: live_secret_values(page)
        )
    except Exception as error:  # noqa: BLE001 - re-raised with the tab's index, type kept
        raise TabReadError(index) from error
    if is_read and values is not None:
        ctx.secret_values[page] = values
        return values
    return ctx.secret_values.get(page, set())


async def scrub_or_refuse(ctx: ActionContext, texts: list[str]) -> list[str]:
    """scrub_secrets for a read tool that matches on or keeps page text: fails closed.

    The snapshot cache, find and wait_for answer match / no-match on this text,
    which would otherwise be a yes/no oracle for a secret that leaked into page
    text, a name or the URL; and the cache is served later, when a changed
    field's old value is no longer live for the tool runner's scrub.

    Raises:
        ActionError: With SCRUB_REFUSAL if the scrub fails (only its type is logged).
    """
    try:
        return await scrub_secrets(ctx, texts)
    except Exception as error:  # noqa: BLE001 - fail closed: never use unscrubbed text
        logger.error("read scrub failed: %s", type(error).__name__)
        raise ActionError(SCRUB_REFUSAL) from None


def _decoded(shown: str) -> str:
    """`shown` percent-decoded and made single-line.

    Decoding lets the scrub find a secret Edge percent-encoded in the path (a
    space as %20, non-ASCII as %C3%A4); replacing control and format characters
    keeps a decoded %0A from faking a new line in the result.
    """
    return replace_unsafe_chars(unquote(shown), UNSAFE_URL_CHAR)


async def shown_url(ctx: ActionContext, url: str) -> str:
    """The form of `url` every tool shows and wait_for matches.

    That is policy.display_url (origin and path), scrubbed, then percent-decoded
    and scrubbed again. The first scrub catches a secret that itself holds a %XX
    (Pa%55word, or an invalid ab%C3) before decoding changes it; the second
    catches one Edge encoded (a space as %20).

    Never raises: if a scrub fails it falls back to the origin alone (no path),
    so a result after an action that ran still comes back and still hides the path.
    """
    try:
        [raw] = await scrub_secrets(ctx, [display_url(url)])
        [shown] = await scrub_secrets(ctx, [_decoded(raw)])
    except Exception as error:  # noqa: BLE001 - fall back to the origin, never the raw path
        logger.error("URL scrub failed: %s", type(error).__name__)
        return origin_of(url)
    return shown
