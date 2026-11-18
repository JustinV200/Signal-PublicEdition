"""Page login: one-time keys from `console open`, traded for a session token the page sends back.

`console open` asks the server (with the local key) for a login key and opens
the page at /#k=<key>. The fragment never reaches a server or a Referer. The
page POSTs it to /api/login once; a key works one time, within
LOGIN_KEY_TTL_S. Each login mints a new random session token, which the page
holds and sends as the X-Console-Token header on every /api call.

A header, not a cookie: browsers send a 127.0.0.1 cookie to every port on
127.0.0.1, so any local listener would receive it. A header only goes where the
page's own script sends it. The server keeps SHA-256 digests of the newest
MAX_SESSIONS tokens, never the tokens. With a digest file (the real server) they
are saved on each login and loaded when SessionAuth is built, before the port
opens, so an open page keeps working across a restart and never sees a 401 while
the server starts.
"""

import hmac
import logging
import secrets
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

from signal_console.server.security.token_digests import load_digests, save_digests, token_digest

log = logging.getLogger(__name__)

SESSION_TOKEN_HEADER = "X-Console-Token"
LOGIN_KEY_TTL_S = 60.0
LOGIN_KEY_BYTES = 32
SESSION_TOKEN_BYTES = 32
# A few open windows at once; logging in past this forgets the oldest token.
MAX_SESSIONS = 8


def secrets_match(supplied: str, expected: str) -> bool:
    """Compare a supplied secret with the real one in constant time.

    Header values that weren't valid UTF-8 arrive holding lone surrogates;
    surrogatepass encodes those too, so they just fail to match instead of raising.
    """
    return hmac.compare_digest(
        supplied.encode("utf-8", "surrogatepass"), expected.encode("utf-8", "surrogatepass")
    )


class SessionAuth:
    """Issues and redeems login keys, and checks page session tokens."""

    def __init__(
        self, digest_file: Path | None = None, clock: Callable[[], float] = time.monotonic
    ) -> None:
        """Start with no keys, and the sessions saved in `digest_file` (if any).

        Args:
            digest_file: Where the token digests are saved; None keeps them in memory only.
            clock: Monotonic seconds, for key expiry (tests pass a fake).
        """
        self._clock = clock
        self._digest_file = digest_file
        self._expiry_by_key: dict[str, float] = {}
        saved = load_digests(digest_file) if digest_file is not None else []
        # deque(maxlen) drops the oldest digest when a new one goes in past the cap.
        self._digests: deque[str] = deque(saved, maxlen=MAX_SESSIONS)

    def issue_login_key(self) -> str:
        """A new single-use login key, valid for LOGIN_KEY_TTL_S."""
        self._drop_expired()
        key = secrets.token_urlsafe(LOGIN_KEY_BYTES)
        self._expiry_by_key[key] = self._clock() + LOGIN_KEY_TTL_S
        return key

    def log_in(self, supplied_key: str) -> str | None:
        """Use up a login key and start a page session.

        Returns:
            A new session token if the key was issued, unused and unexpired, else None.
        """
        if not self._redeem(supplied_key):
            return None
        token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        self._digests.append(token_digest(token))
        self._save_digests()
        return token

    def is_session_token(self, supplied: str) -> bool:
        """True if `supplied` is one of the live session tokens."""
        supplied_digest = token_digest(supplied)
        # Check every digest, so the time taken doesn't say which one matched.
        results = [secrets_match(supplied_digest, digest) for digest in self._digests]
        return any(results)

    def _save_digests(self) -> None:
        if self._digest_file is None:
            return
        # Runs in the event loop: two icacls runs per login (one per `console open`), cheap enough.
        try:
            save_digests(self._digest_file, list(self._digests))
        except OSError:
            # The new window still works; it just won't survive the next restart.
            log.warning("couldn't save session digests to %s", self._digest_file, exc_info=True)

    def _redeem(self, supplied: str) -> bool:
        self._drop_expired()
        # Compare against every live key in constant time; there are only a few.
        matches = [key for key in self._expiry_by_key if secrets_match(supplied, key)]
        for key in matches:
            del self._expiry_by_key[key]
        return bool(matches)

    def _drop_expired(self) -> None:
        now = self._clock()
        for key in [key for key, expiry in self._expiry_by_key.items() if expiry <= now]:
            del self._expiry_by_key[key]
