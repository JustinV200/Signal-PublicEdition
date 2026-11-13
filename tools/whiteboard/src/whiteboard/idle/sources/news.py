"""The NEWS ticker: the top headlines from an RSS 2.0 or Atom feed, picked by a fixed rule.

The first MAX_HEADLINES items (RSS `<item>`, Atom `<entry>`) in feed order (the editor's
ranking) with a title and a date in the last FRESH_FOR (RSS pubDate; Atom published, else
updated); an item with no readable date counts as fresh, and a title already picked
isn't repeated. No model and no summary: only the titles are shown, scrolling beside
the source's name.

The feed is outside text, so it's treated as hostile (plan.md section 2):
- a body over MAX_FEED_BYTES, with a DOCTYPE (entity tricks), or in an encoding that isn't
  ASCII-compatible (a UTF-16/32 byte-order mark, or any NUL byte), is refused before
  parsing: in UTF-16 a DOCTYPE wouldn't show up in a byte search, but expat would read it;
- only each item's title and date are read (xml.etree; Python 3.12's expat guards
  against entity expansion, and the DOCTYPE check rules the rest out);
- each title is cleaned (tags stripped, unescaped, control characters dropped, one line)
  and cut to MAX_HEADLINE_CHARS, and the page sets it as text, with no link.
"""

import codecs
import re
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterator
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from whiteboard.idle.text import clean_text

MAX_FEED_BYTES = 512 * 1024
MAX_HEADLINE_CHARS = 140
# Enough to fill a few minutes of the ticker; a lap at 75 px/s takes about 4 minutes.
MAX_HEADLINES = 6
FRESH_FOR = timedelta(hours=24)
_DOCTYPE = re.compile(rb"<!DOCTYPE", re.IGNORECASE)
_ATOM = "{http://www.w3.org/2005/Atom}"


# UTF-32 marks first: the UTF-32 LE mark starts with the UTF-16 LE one.
_WIDE_BOMS = (codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE, codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)


class NewsError(ValueError):
    """The feed was refused: too big, not ASCII-compatible, has a DOCTYPE, or isn't XML."""


def parse_headlines(body: bytes, now: datetime) -> list[str]:
    """The headlines to show, in feed order: empty if the feed has no fresh titled item.

    Args:
        body: The feed as fetched (at most MAX_FEED_BYTES + 1 bytes are needed).
        now: The current time (aware), for freshness.

    Raises:
        NewsError: See the class.
    """
    if len(body) > MAX_FEED_BYTES:
        raise NewsError(f"feed over {MAX_FEED_BYTES} bytes")
    # Expat reads UTF-8, Latin-1, ASCII or UTF-16; only UTF-16 (and UTF-32) hide markup
    # from a byte search, and they can't be written without a NUL byte or a BOM.
    if body.startswith(_WIDE_BOMS) or b"\x00" in body:
        raise NewsError("feed isn't in an ASCII-compatible encoding")
    if _DOCTYPE.search(body):
        raise NewsError("feed has a DOCTYPE")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as error:
        raise NewsError(f"feed isn't XML: {error}") from error
    headlines: list[str] = []
    for raw_title, published in _items(root):
        title = clean_text(raw_title, MAX_HEADLINE_CHARS)
        is_fresh = published is None or now - published <= FRESH_FOR
        if title and is_fresh and title not in headlines:
            headlines.append(title)
            if len(headlines) == MAX_HEADLINES:
                break
    return headlines


def _items(root: ElementTree.Element) -> Iterator[tuple[str, datetime | None]]:
    """Each item's (raw title, aware date or None), in feed order, RSS 2.0 or Atom."""
    if root.tag == f"{_ATOM}feed":
        for entry in root.iterfind(f"{_ATOM}entry"):
            stamp = entry.findtext(f"{_ATOM}published") or entry.findtext(f"{_ATOM}updated")
            yield entry.findtext(f"{_ATOM}title") or "", _iso_date(stamp)
        return
    for item in root.iterfind("channel/item"):
        yield item.findtext("title") or "", _rfc822_date(item.findtext("pubDate"))


def _rfc822_date(value: str | None) -> datetime | None:
    """An RSS pubDate as an aware datetime, or None if missing or unreadable."""
    try:
        moment = parsedate_to_datetime(value) if value else None
    except (TypeError, ValueError):
        return None
    return moment if moment is not None and moment.tzinfo else None


def _iso_date(value: str | None) -> datetime | None:
    """An Atom (RFC 3339) date as an aware datetime, or None if missing or unreadable."""
    try:
        moment = datetime.fromisoformat(value.strip()) if value else None
    except ValueError:
        return None
    return moment if moment is not None and moment.tzinfo else None
