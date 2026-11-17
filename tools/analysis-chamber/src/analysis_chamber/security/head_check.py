"""Decide which URLs are data downloads: by shape first, then a bounded HEAD check.

page_fetch_hook asks page_urls for every URL in a fetching command or script. The
shape rules (data suffix, data-format query, known data API host) need no network.
Each other URL gets one HEAD request: at most MAX_HEAD_CHECKS of them, run in parallel
under one HEAD_DEADLINE_S deadline. A URL left unchecked, or whose check fails, counts
as a page, so the fetch is denied.

TODO: a server that lies about Content-Type, or a data URL whose body is a page.
"""

import logging
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from urllib.parse import urlsplit

from analysis_chamber.security.rules.fetch_rules import (
    DATA_CONTENT_TYPES,
    DATA_HOSTS,
    DATA_QUERY,
    DATA_SUFFIXES,
    HEAD_DEADLINE_S,
    HEAD_TIMEOUT_S,
    MAX_HEAD_CHECKS,
    TEMPLATE_MARKERS,
)

logger = logging.getLogger(__name__)

# url -> Content-Type header, or None when it can't be found out.
ContentTypeChecker = Callable[[str], str | None]

# Punctuation that ends a sentence or argument list, not the URL.
_URL_TRAILING = ".,;"


def head_content_type(url: str) -> str | None:
    """Default checker: the Content-Type from a short HEAD request, or None on failure.

    A failure means the hook blocks the fetch, so it's logged, not raised.
    """
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=HEAD_TIMEOUT_S) as response:
            return response.headers.get("Content-Type")
    except urllib.error.HTTPError as error:
        # An error status (405 for HEAD, 403) still carries a usable Content-Type.
        return error.headers.get("Content-Type")
    except (urllib.error.URLError, OSError, ValueError) as error:
        logger.warning("HEAD %s failed, treating it as a page: %s", url, error)
        return None


def is_data_content_type(content_type: str) -> bool:
    """Whether a Content-Type header names a data format (incl. any +json type)."""
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type.endswith("+json") or media_type.startswith(DATA_CONTENT_TYPES)


def is_data_by_shape(url: str) -> bool:
    """Whether a URL is a data download by its suffix, query or host alone."""
    parts = urlsplit(url)
    if parts.path.lower().endswith(DATA_SUFFIXES) or DATA_QUERY.search(parts.query):
        return True
    host_and_path = parts.netloc.lower() + parts.path
    return any(pattern.fullmatch(host_and_path) for pattern in DATA_HOSTS)


def _is_data_result(future: "Future[str | None]", url: str) -> bool:
    """Whether a finished HEAD check says data; a checker error counts as a page."""
    error = future.exception()
    if error is not None:
        logger.warning("HEAD check of %s raised, treating it as a page: %s", url, error)
        return False
    return is_data_content_type(future.result() or "")


def _head_check_pages(urls: list[str], checker: ContentTypeChecker) -> list[str]:
    """The URLs whose HEAD check doesn't say data, or doesn't finish by the deadline."""
    if not urls:
        return []
    executor = ThreadPoolExecutor(max_workers=len(urls))
    futures = {executor.submit(checker, url): url for url in urls}
    done, _ = wait(futures, timeout=HEAD_DEADLINE_S)
    # Don't wait for stragglers: the hook answers now, a late HEAD just finishes alone.
    executor.shutdown(wait=False, cancel_futures=True)
    return [
        url
        for future, url in futures.items()
        if future not in done or not _is_data_result(future, url)
    ]


def page_urls(urls: Iterable[str], checker: ContentTypeChecker) -> list[str]:
    """The URLs that aren't data downloads, or couldn't be checked in time.

    Args:
        urls: URL literals found in the code.
        checker: Content-Type lookup for URLs the shape rules can't settle.

    Returns:
        The page (or unchecked) URLs; empty when every URL is data.
    """
    unsettled = [
        url
        for url in dict.fromkeys(u.rstrip(_URL_TRAILING) for u in urls)
        if not is_data_by_shape(url)
    ]
    # Built at run time (f-string, $var, %-format): a HEAD would test the wrong address.
    pages = [url for url in unsettled if TEMPLATE_MARKERS.search(url)]
    to_check = [url for url in unsettled if url not in pages]
    pages += to_check[MAX_HEAD_CHECKS:]
    return pages + _head_check_pages(to_check[:MAX_HEAD_CHECKS], checker)
