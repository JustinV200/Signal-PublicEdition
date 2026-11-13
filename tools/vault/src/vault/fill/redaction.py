"""Keep filled values out of what the browser tool returns: the snapshot gate and the text scrubber.

Playwright's aria snapshot prints every input's value, password inputs
included, so the browser tool must refuse snapshots and screenshots while
`page_has_filled_fields` is True. `scrub_text` is the exact-match backstop for
any other text it returns.
"""

import html
import json
import re
from collections.abc import Iterable
from urllib.parse import quote, quote_plus

from vault.fill.fields import PASSWORD_SELECTOR
from vault.fill.page_protocol import PageLike
from vault.fill.registry import FilledRegistry
from vault.secret import Secret

REDACTION_MARK = "[vault-redacted]"
FIELD_GONE = "gone"
FIELD_FILLED = "filled"

# Run in the page against a vault-filled element.
FIELD_STATE_JS = (
    f"(input) => !input.isConnected ? '{FIELD_GONE}'"
    f" : (input.value !== '' ? '{FIELD_FILLED}' : 'empty')"
)
# Run in each frame against all password inputs.
ANY_NON_EMPTY_JS = "(inputs) => inputs.some((input) => input.value !== '')"


async def _registered_field_holds_value(page: PageLike, registry: FilledRegistry) -> bool:
    """True if any element the vault filled is still attached and non-empty. Prunes gone ones."""
    for handle in registry.handles(page):
        try:
            state = await handle.evaluate(FIELD_STATE_JS)
        except Exception:
            # Disposed handle or destroyed context: the element went with its page.
            state = FIELD_GONE
        if state == FIELD_FILLED:
            return True
        if state == FIELD_GONE:
            registry.drop_handle(page, handle)
    return False


async def _any_password_input_has_value(page: PageLike) -> bool:
    """True if any password input in any frame is non-empty. Fails closed on errors."""
    for frame in page.frames:
        try:
            if await frame.eval_on_selector_all(PASSWORD_SELECTOR, ANY_NON_EMPTY_JS):
                return True
        except Exception:
            # A frame we can't inspect (mid-navigation, detached) might hold a password;
            # refusing one snapshot is cheaper than leaking one.
            return True
    return False


async def page_has_filled_fields(page: PageLike, registry: FilledRegistry) -> bool:
    """Return True while snapshots/screenshots of `page` could show a secret.

    True if a vault-filled field is still attached and non-empty, or if any
    password input on the page (vault-filled or typed by hand) is non-empty.
    """
    if await _registered_field_holds_value(page, registry):
        return True
    return await _any_password_input_has_value(page)


def _encoded_forms(value: str) -> set[str]:
    """The value plus the encodings it commonly shows up in (JSON, URL, HTML)."""
    return {
        value,
        json.dumps(value)[1:-1],
        json.dumps(value, ensure_ascii=False)[1:-1],
        quote(value, safe=""),
        quote_plus(value),
        html.escape(value),
        html.escape(value, quote=False),
    }


def scrub_text(text: str, secrets: Iterable[Secret]) -> str:
    """Replace every occurrence of each secret (and its common encodings) with REDACTION_MARK.

    One regex pass, longest pattern first, so a short secret can't match inside
    a longer one's replacement.

    Args:
        text: Text the browser tool is about to return.
        secrets: The secrets to remove.

    Returns:
        The scrubbed text (unchanged if there are no secrets).
    """
    forms = {form for secret in secrets for form in _encoded_forms(secret.reveal()) if form}
    if not forms:
        return text
    pattern = re.compile("|".join(re.escape(form) for form in sorted(forms, key=len, reverse=True)))
    return pattern.sub(REDACTION_MARK, text)
