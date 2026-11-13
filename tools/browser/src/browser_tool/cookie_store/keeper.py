"""CookieKeeper: saves a browser's cookies on a clean close and adds them back at launch.

Two modes:
- OWN (the desktop MCP server's browser): at launch, add back the saved
  session cookies only, since the profile keeps its persistent ones (and may
  hold newer values); on a clean close, save every cookie.
- BORROW (visit mode, the checker): at launch, add back every unexpired saved
  cookie its own, stricter policy allows; never save. This is how the checker
  shares the desktop's sign-in: two Edges can't open one profile at once.

The file is a DPAPI blob (CurrentUser) of JSON, owner-only (secret_file). It
never fails a launch or a close: a missing file is silent, and an unreadable,
undecryptable or malformed one is ignored with a log line naming the error's
type only. No cookie name, value or domain is ever logged.
"""

import json
import logging
import time
from collections.abc import Callable
from enum import Enum
from pathlib import Path

from playwright.async_api import BrowserContext
from playwright.async_api import Error as PlaywrightError

from browser_tool.cookie_store.cookie_filter import Cookie, parse_saved, restorable, to_saved
from browser_tool.cookie_store.dpapi import DpapiError, protect, unprotect
from browser_tool.cookie_store.secret_file import write_owner_only
from browser_tool.policy import HostPolicy

logger = logging.getLogger(__name__)

# Ties the blob to this use: another DPAPI blob of the same user won't decrypt here.
DPAPI_ENTROPY = b"signal-browser-cookies-v1"
ENCODING = "utf-8"


class CookieMode(Enum):
    """How a browser uses the saved cookies (see the module docstring)."""

    OWN = "own"
    BORROW = "borrow"


class CookieKeeper:
    """One browser's use of the saved-cookies file."""

    def __init__(
        self,
        path: Path,
        policy: HostPolicy,
        mode: CookieMode,
        clock: Callable[[], float] = time.time,
    ):
        """Nothing is read or written until restore() or save().

        Args:
            path: The saved-cookies file ([browser] cookie_file, resolved).
            policy: The browser's host policy; only cookies for hosts it allows come back.
            mode: OWN or BORROW.
            clock: Unix seconds, for expiry; tests pass a fake.
        """
        self._path = path
        self._policy = policy
        self._mode = mode
        self._clock = clock

    async def restore(self, context: BrowserContext) -> None:
        """Add the saved cookies this browser may have to `context`. Never raises."""
        cookies = self._read()
        is_own = self._mode is CookieMode.OWN
        chosen = restorable(cookies, self._policy, self._clock(), session_only=is_own)
        if not chosen:
            return
        try:
            await context.add_cookies(chosen)  # type: ignore[arg-type]
        except PlaywrightError as error:
            logger.warning("saved cookies weren't restored: %s", type(error).__name__)
            return
        logger.info("restored %d of %d saved cookies", len(chosen), len(cookies))

    async def save(self, context: BrowserContext) -> None:
        """Save `context`'s cookies, in OWN mode only (BORROW never writes). Never raises."""
        if self._mode is not CookieMode.OWN:
            return
        try:
            document = to_saved(await context.cookies())
            text = json.dumps(document, ensure_ascii=False)
            write_owner_only(self._path, protect(text.encode(ENCODING), DPAPI_ENTROPY))
        except (PlaywrightError, DpapiError, OSError) as error:
            logger.warning("cookies weren't saved: %s", type(error).__name__)
            return
        logger.info("saved %d cookies", len(document["cookies"]))

    def _read(self) -> list[Cookie]:
        """The saved cookies, or [] when there's no usable file."""
        try:
            blob = self._path.read_bytes()
        except FileNotFoundError:
            return []
        except OSError as error:
            logger.warning("the saved cookies can't be read: %s", type(error).__name__)
            return []
        try:
            # ValueError covers bad UTF-8, bad JSON and CookieFileError.
            return parse_saved(json.loads(unprotect(blob, DPAPI_ENTROPY).decode(ENCODING)))
        except (DpapiError, ValueError, RecursionError) as error:
            logger.warning("ignoring the saved cookies file: %s", type(error).__name__)
            return []
