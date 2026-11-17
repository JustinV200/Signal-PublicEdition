"""One blocking HTTP GET that never follows redirects, for the downloader and robots.txt.

Redirects come back as a 3xx Response with its Location, so the async caller can
check each hop (scheme, robots.txt, rate limit) before following it. Nothing a
server sends reaches the lead from here except a content type that passed
CONTENT_TYPE_PATTERN; error text is fixed (the status code or the exception type).
"""

import http.client
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

USER_AGENT = "analysis-chamber/0.1 (+personal research tool)"
TIMEOUT_S = 60
# A bare media type; anything else (spaces, quotes, prose) is dropped as "".
CONTENT_TYPE_PATTERN = re.compile(r"[a-z0-9.+-]+/[a-z0-9.+-]+")
# RFC 3986 reserved characters plus `%`, left as they are by encode_url.
_URL_SAFE_CHARS = ":/?#[]@!$&'()*+,;=%~"


class FetchError(Exception):
    """A URL couldn't be fetched. The message is fixed text, never server text."""


def unexpected_error(error: Exception) -> FetchError:
    """Log an unexpected error server-side and return a fixed-text FetchError for it.

    The boundary for the downloader and robots.txt cache: urllib, idna and
    robotparser raise ValueError and friends on odd URLs, and their text can
    carry server input, so only the type name goes into the message.
    """
    logger.warning("unexpected fetch error", exc_info=error)
    return FetchError(f"bad URL or response ({type(error).__name__})")


@dataclass(frozen=True)
class Response:
    """One HTTP response, redirects not followed.

    Attributes:
        status: The HTTP status code.
        content_type: The checked media type without parameters ("" if none or bad).
        body: Up to the caller's byte limit ("" for error statuses).
        location: The Location header of a 3xx ("" otherwise).
    """

    status: int
    content_type: str
    body: bytes
    location: str = ""


# (url, max_bytes, timeout_s) -> Response. Raises OSError on network failure.
HttpGet = Callable[[str, int, float], Response]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hands 3xx back as HTTPError so the caller checks each hop itself.

    The http_error_3xx methods are overridden, not just redirect_request: the
    base class parses Location before redirect_request runs, and a bad one
    (e.g. "http://[bad/x") would raise there. Returning None sends the status
    on to the default handler, which raises HTTPError with the raw headers.
    """

    def _no_redirect(self, req, fp, code, msg, headers):  # noqa: ANN001, ANN202
        return None

    http_error_301 = http_error_302 = http_error_303 = _no_redirect
    http_error_307 = http_error_308 = _no_redirect


_OPENER = urllib.request.build_opener(_NoRedirect)


def clean_content_type(header: str | None) -> str:
    """The media type of a Content-Type header, lowercased, or "" if it isn't a bare type."""
    media_type = (header or "").split(";", 1)[0].strip().lower()
    return media_type if CONTENT_TYPE_PATTERN.fullmatch(media_type) else ""


def encode_url(url: str) -> str:
    """Percent-encode characters http.client refuses (spaces, non-ASCII) in `url`.

    Real links often hold them (a PDF named "Factors Driving Prices.pdf"), and
    http.client raises InvalidURL on them. Reserved characters and existing `%xx`
    escapes are kept, so an already-encoded URL comes back unchanged. The host is
    left alone (idna handles it).
    """
    parts = urllib.parse.urlsplit(url)
    path, query, fragment = (
        urllib.parse.quote(part, safe=_URL_SAFE_CHARS)
        for part in (parts.path, parts.query, parts.fragment)
    )
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, fragment))


def http_get(url: str, max_bytes: int, timeout_s: float = TIMEOUT_S) -> Response:
    """Blocking GET of `url`, reading at most `max_bytes` of the body.

    Args:
        url: An http(s) URL (the caller checks the scheme).
        max_bytes: The most body bytes to read; read one more to detect "too big".
        timeout_s: Socket timeout.

    Returns:
        The response; HTTP error and redirect statuses come back, not raised.

    Raises:
        OSError: Network failure or timeout (URLError is an OSError), or a URL or
            response urllib/idna/http.client couldn't handle (fixed text).
    """
    request = urllib.request.Request(encode_url(url), headers={"User-Agent": USER_AGENT})
    try:
        with _OPENER.open(request, timeout=timeout_s) as response:
            body = response.read(max_bytes)
            content_type = clean_content_type(response.headers.get("Content-Type"))
            return Response(response.status, content_type, body)
    except urllib.error.HTTPError as error:
        location = error.headers.get("Location", "") if error.headers else ""
        error.close()
        return Response(error.code, "", b"", location)
    except (ValueError, http.client.HTTPException) as error:
        # e.g. a host idna rejects, or a malformed status line; callers expect OSError.
        raise OSError(f"bad URL or response ({type(error).__name__})") from error
