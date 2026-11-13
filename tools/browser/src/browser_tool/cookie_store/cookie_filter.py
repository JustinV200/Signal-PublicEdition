"""Which cookies are saved, and which saved ones may go back into a browser. Pure Python.

Saved: every cookie Playwright reports, cut to the fields add_cookies takes,
except one missing a field and partitioned (CHIPS) cookies, which would lose
their partition and widen their reach if restored.

Restored: only from a file of the expected shape (parse_saved, else the whole
file is refused), only unexpired, and only for a host the loading browser's own
policy allows. A domain cookie (".google.com") also counts when an allowlisted
host sits under it (accounts.google.com), since that host is sent it.
"""

import math
from collections.abc import Iterable
from typing import Any

from browser_tool.policy import HostPattern, HostPolicy

FORMAT_VERSION = 1
# Playwright's expires for a session cookie (gone when the browser closes).
SESSION_EXPIRES = -1
SAVED_KEYS = ("name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite")
SAME_SITE_VALUES = frozenset({"Strict", "Lax", "None"})
# A made-up first label, to ask the policy about the hosts a "*.example.com" pattern allows.
WILDCARD_PROBE_LABEL = "a"

Cookie = dict[str, Any]


class CookieFileError(ValueError):
    """The saved cookies aren't the expected shape. The message never holds a cookie."""


def to_saved(cookies: Iterable[Cookie]) -> dict[str, Any]:
    """The JSON-ready document for `cookies` (as BrowserContext.cookies() returns them)."""
    kept = [
        {key: cookie[key] for key in SAVED_KEYS if key in cookie}
        for cookie in cookies
        if not cookie.get("partitionKey") and all(key in cookie for key in SAVED_KEYS)
    ]
    return {"version": FORMAT_VERSION, "cookies": kept}


def parse_saved(data: object) -> list[Cookie]:
    """The cookies in a saved document, every one checked.

    Raises:
        CookieFileError: The document or any cookie in it isn't the expected shape.
    """
    if not isinstance(data, dict) or data.get("version") != FORMAT_VERSION:
        raise CookieFileError("not a saved-cookies document of this version")
    cookies = data.get("cookies")
    if not isinstance(cookies, list) or not all(_is_well_formed(c) for c in cookies):
        raise CookieFileError("a saved cookie isn't the expected shape")
    return [{key: cookie[key] for key in SAVED_KEYS} for cookie in cookies]


def restorable(
    cookies: Iterable[Cookie], policy: HostPolicy, now: float, *, session_only: bool
) -> list[Cookie]:
    """The cookies that may be added back to a browser running under `policy`.

    Args:
        cookies: Checked cookies (parse_saved).
        policy: The loading browser's host policy.
        now: The current Unix time in seconds.
        session_only: Keep only session cookies (the profile that saved them
            still holds its persistent ones, maybe newer).
    """
    return [
        cookie
        for cookie in cookies
        if _is_live(cookie, now, session_only) and is_cookie_host_allowed(cookie["domain"], policy)
    ]


def is_cookie_host_allowed(domain: str, policy: HostPolicy) -> bool:
    """True when `policy` allows the cookie's host, or (domain cookie) an allowed host under it."""
    host = domain.removeprefix(".")
    if policy.check_host(host).is_allowed:
        return True
    if not domain.startswith("."):
        return False
    return any(_allows_host_under(pattern, host, policy) for pattern in policy.allow_patterns)


def _allows_host_under(pattern: HostPattern, host: str, policy: HostPolicy) -> bool:
    """True when `pattern` allows some host under `host` that the policy doesn't deny."""
    probe = pattern.host
    if pattern.is_subdomain_wildcard:
        probe = f"{WILDCARD_PROBE_LABEL}.{pattern.host}"
    return probe.endswith("." + host) and policy.check_host(probe).is_allowed


def _is_live(cookie: Cookie, now: float, session_only: bool) -> bool:
    """True for a session cookie, or (unless session_only) one that hasn't expired."""
    if cookie["expires"] == SESSION_EXPIRES:
        return True
    return not session_only and cookie["expires"] > now


def _is_well_formed(cookie: object) -> bool:
    """True when `cookie` has every saved field, each of the right type."""
    if not isinstance(cookie, dict) or not all(key in cookie for key in SAVED_KEYS):
        return False
    texts = (cookie["name"], cookie["value"], cookie["domain"], cookie["path"])
    if not all(isinstance(text, str) for text in texts) or not cookie["domain"]:
        return False
    expires = cookie["expires"]
    is_number = isinstance(expires, int | float) and not isinstance(expires, bool)
    if not is_number or not math.isfinite(expires):
        return False
    flags = (cookie["httpOnly"], cookie["secure"])
    same_site = cookie["sameSite"]
    is_same_site = isinstance(same_site, str) and same_site in SAME_SITE_VALUES
    return all(isinstance(flag, bool) for flag in flags) and is_same_site
