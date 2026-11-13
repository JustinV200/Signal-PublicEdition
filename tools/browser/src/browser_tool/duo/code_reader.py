"""Reads the verification code a Duo "Verified Push" prompt shows. Read only.

With Verified Push, the Duo prompt shows a short number that the owner types
into Duo Mobile before approving. This module only reads text Duo displays; it
never clicks or types, and the acting tools' Duo lockout is unchanged.

The heuristic fails closed:
- Only a tab whose top-level page is on Duo is read: the Universal Prompt, which
  Duo doesn't allow in an iframe. Within it, only frames on a Duo host with a
  readable hostname (is_duo_url plus host_of) whose every ancestor up to the top
  page is one too. A Duo frame embedded by any other page, or nested inside a
  non-Duo frame, is never read: that page or frame is Duo's parent, gets Duo's
  result back, and may not belong to the site being logged in to. Non-Duo
  frames, blob: frames and Duo-ish URLs whose host can't be parsed are ignored,
  whatever they show.
- A candidate is a visible text node that is exactly 3-6 ASCII digits, near
  Duo's code wording: "code", "enter" or "verification" in the node's element
  or one of its MAX_ANCESTOR_LEVELS ancestors. Each of those counts through its
  aria-label and aria-labelledby text, and through its own text while that is
  at most MAX_CONTEXT_CHARS long (so the wording of the whole page doesn't count).
- Exactly one distinct candidate across all Duo frames is the code. None, two
  or more, or a frame that can't be read (or replies with anything but a short
  list of digit strings) means no code this time.
"""

import re

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Frame, Page

from browser_tool.duo.hosts import is_duo_url
from browser_tool.policy import host_of

MIN_CODE_DIGITS = 3
MAX_CODE_DIGITS = 6
# ASCII digits only: Python's \d would also match other scripts' digits.
VERIFICATION_CODE_RE = re.compile(f"[0-9]{{{MIN_CODE_DIGITS},{MAX_CODE_DIGITS}}}")
MAX_ANCESTOR_LEVELS = 3
MAX_CONTEXT_CHARS = 300
# A frame reporting more than this is not showing one code.
MAX_CANDIDATES = 10

# Runs in each Duo frame. Limits come in as `opts` (one source with the Python side),
# so no JS braces need escaping.
_CANDIDATES_JS = r"""(opts) => {
  const CODE_RE = new RegExp(`^[0-9]{${opts.minDigits},${opts.maxDigits}}$`);
  const WORDING_RE = /\b(code|enter|verification)\b/i;
  const isShown = (el) => el.checkVisibility({
    opacityProperty: true, visibilityProperty: true, checkOpacity: true, checkVisibilityCSS: true,
  });
  const namesOf = (el) => {
    const ids = (el.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean);
    const labels = ids.map((id) => document.getElementById(id)?.textContent);
    return [el.getAttribute('aria-label'), ...labels].filter(Boolean).join(' ');
  };
  const isNearWording = (el) => {
    for (let node = el, level = 0; node && level <= opts.maxLevels; node = node.parentElement) {
      if (WORDING_RE.test(namesOf(node))) return true;
      const text = node.textContent || '';
      if (text.length > opts.maxContextChars) return false;
      if (WORDING_RE.test(text)) return true;
      level += 1;
    }
    return false;
  };
  const found = [];
  const root = document.body || document.documentElement;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.textContent.trim();
    const el = node.parentElement;
    if (!CODE_RE.test(text) || !el || !isShown(el) || !isNearWording(el)) continue;
    found.push(text);
    if (found.length > opts.maxCandidates) break;
  }
  return found;
}"""
_JS_OPTIONS = {
    "minDigits": MIN_CODE_DIGITS,
    "maxDigits": MAX_CODE_DIGITS,
    "maxLevels": MAX_ANCESTOR_LEVELS,
    "maxContextChars": MAX_CONTEXT_CHARS,
    "maxCandidates": MAX_CANDIDATES,
}


async def read_verification_code(page: Page) -> str | None:
    """The verification code the tab's Duo frames show, if there is exactly one.

    Args:
        page: A tab in a Duo prompt. Nothing is read unless its top-level page is on Duo.

    Returns:
        The code, MIN_CODE_DIGITS to MAX_CODE_DIGITS ASCII digits, or None when
        there is no single clear code (see the module docstring), including when a
        Duo frame can't be read.
    """
    if not _is_readable_duo_url(page.main_frame.url):
        return None
    candidates: set[str] = set()
    for frame in page.frames:
        if not _is_duo_all_the_way_up(frame):
            continue
        try:
            found = await frame.evaluate(_CANDIDATES_JS, _JS_OPTIONS)
        except PlaywrightError:
            # Detached or mid-navigation: what it shows is unknown, so no code this round.
            return None
        codes = _codes_from(found)
        if codes is None:
            return None
        candidates |= codes
    return next(iter(candidates)) if len(candidates) == 1 else None


def _is_duo_all_the_way_up(frame: Frame) -> bool:
    """True when this frame and every frame above it, the top page included, are on Duo."""
    node: Frame | None = frame
    while node is not None:
        if not _is_readable_duo_url(node.url):
            return False
        node = node.parent_frame
    return True


def _is_readable_duo_url(url: str) -> bool:
    """A Duo URL with a hostname that parses (is_duo_url alone also passes unreadable ones)."""
    return is_duo_url(url) and host_of(url) is not None


def _codes_from(found: object) -> set[str] | None:
    """The codes one frame reported, or None if its reply isn't a short list of codes."""
    if not isinstance(found, list) or len(found) > MAX_CANDIDATES:
        return None
    if not all(isinstance(item, str) and VERIFICATION_CODE_RE.fullmatch(item) for item in found):
        return None
    return set(found)
