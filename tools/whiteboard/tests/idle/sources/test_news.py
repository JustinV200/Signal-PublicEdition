"""parse_headlines: the first fresh titled items, and a hostile feed refused or defanged."""

from datetime import UTC, datetime

import pytest

from whiteboard.idle import MAX_FEED_BYTES, MAX_HEADLINES, NewsError, parse_headlines

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
FRESH = "Tue, 20 Oct 2026 09:00:00 GMT"
# Written as chr() so the source itself holds no invisible character.
ZERO_WIDTH_SPACE = chr(0x200B)
UTF16_DOCTYPE = (
    '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE r [<!ENTITY a "boom">]>'
    "<rss><channel><item><title>&a;</title></item></channel></rss>"
)
STALE = "Sun, 18 Oct 2026 09:00:00 GMT"


def feed(*items: tuple[str, str | None]) -> bytes:
    body = "".join(
        f"<item><title>{title}</title>{f'<pubDate>{date}</pubDate>' if date else ''}</item>"
        for title, date in items
    )
    return f'<?xml version="1.0"?><rss><channel>{body}</channel></rss>'.encode()


def atom(*entries: tuple[str, str]) -> bytes:
    body = "".join(
        f"<entry><title type='html'>{title}</title><updated>{stamp}</updated></entry>"
        for title, stamp in entries
    )
    return f'<feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'.encode()


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (feed(("First", FRESH), ("Second", FRESH)), ["First", "Second"]),
        # Stale, empty and repeated titles are skipped, in feed order.
        (
            feed(("Old news", STALE), ("", FRESH), ("Fresh one", FRESH), ("Fresh one", FRESH)),
            ["Fresh one"],
        ),
        (feed(("No date", None)), ["No date"]),
        (feed(("Old news", STALE)), []),
        # Only the top MAX_HEADLINES.
        (
            feed(*((f"Story {n}", FRESH) for n in range(MAX_HEADLINES + 3))),
            [f"Story {n}" for n in range(MAX_HEADLINES)],
        ),
        # Escaped markup, CDATA and control characters come out as one line of plain text.
        (
            feed(("&lt;b&gt;Big&lt;/b&gt; &amp;" + ZERO_WIDTH_SPACE + "\x7f  news\n\tday", FRESH)),
            ["Big & news day"],
        ),
        (feed(("<![CDATA[<img src=x onerror=alert(1)>Rates held]]>", FRESH)), ["Rates held"]),
        (feed(("x" * 500, FRESH)), ["x" * 139 + "…"]),
        # Atom: entries, updated dates (RFC 3339), escaped HTML titles.
        (
            atom(
                ("Old", "2026-10-18T09:00:00Z"), ("A &lt;i&gt;lead&lt;/i&gt;", "2026-10-20T09:00Z")
            ),
            ["A lead"],
        ),
    ],
)
def test_picks_the_first_fresh_items_as_clean_text(body: bytes, expected: list[str]) -> None:
    assert parse_headlines(body, NOW) == expected


@pytest.mark.parametrize(
    "body",
    [
        b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss/>',
        b"<!doctype html><html></html>",
        b"<rss>" + b" " * MAX_FEED_BYTES + b"</rss>",
        b"not xml at all",
        # A DOCTYPE in UTF-16 escapes a byte search, but expat would expand its entity.
        UTF16_DOCTYPE.encode("utf-16"),
        UTF16_DOCTYPE.encode("utf-16-le"),
    ],
    ids=["entity", "html", "oversized", "not-xml", "utf16-bom", "utf16-no-bom"],
)
def test_refuses_doctype_oversized_and_broken_feeds(body: bytes) -> None:
    with pytest.raises(NewsError):
        parse_headlines(body, NOW)
