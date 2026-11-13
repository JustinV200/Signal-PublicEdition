"""The only code that hands plaintext to Playwright, plus the submit key press after it.

Playwright writes `fill("<value>")` into each action's call log, and the call
log goes into error messages (a timeout, a detached element). So any
exception from these calls may contain the secret. They are caught here,
discarded without logging, and turned into a bare False. Nothing is
re-raised: `raise ... from None` would still keep the original as
`__context__`.

Cancellation is the one exception that must propagate. A fresh
CancelledError is raised *outside* the except block, so it carries no
`__context__` pointing at a Playwright error.
"""

import asyncio
from collections.abc import Awaitable, Sequence

from vault.fill.page_protocol import ElementLike
from vault.secret import Secret

FILL_TIMEOUT_MS = 5000
SUBMIT_KEY = "Enter"


async def _succeeds_quietly(action: Awaitable[None]) -> bool:
    """Await `action`; return True on success and False on any error, which is discarded.

    Raises:
        asyncio.CancelledError: A fresh one, with no chained context, if cancelled.
    """
    is_cancelled = False
    succeeded = False
    try:
        await action
        succeeded = True
    except asyncio.CancelledError:
        is_cancelled = True
    except Exception:
        # Deliberately discarded, never logged: the message and call log can hold the secret.
        succeeded = False
    if is_cancelled:
        raise asyncio.CancelledError
    return succeeded


async def _fill_all(targets: Sequence[tuple[ElementLike, Secret]]) -> None:
    for handle, secret in targets:
        await handle.fill(secret.reveal(), timeout=FILL_TIMEOUT_MS)


async def fill_without_leaks(targets: Sequence[tuple[ElementLike, Secret]]) -> bool:
    """Fill each ElementHandle with its secret, in order.

    Args:
        targets: (ElementHandle, secret) pairs.

    Returns:
        True if every fill succeeded; False if any failed (the error is discarded).

    Raises:
        asyncio.CancelledError: A fresh one, with no chained context, if cancelled.
    """
    return await _succeeds_quietly(_fill_all(targets))


async def press_submit_without_leaks(password_field: ElementLike) -> bool:
    """Press Enter in the password field to submit the form.

    Returns:
        True if the key press went through; False on any error (discarded, as above).

    Raises:
        asyncio.CancelledError: A fresh one, with no chained context, if cancelled.
    """
    return await _succeeds_quietly(password_field.press(SUBMIT_KEY, timeout=FILL_TIMEOUT_MS))
