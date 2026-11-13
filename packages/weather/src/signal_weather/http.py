"""get_json: one small HTTPS GET that returns parsed JSON, with a timeout and a size cap.

Both lookups in this package (Open-Meteo, the IP location service) are keyless JSON
GETs, so they share this. Blocking (urllib): async callers run it in a thread.
"""

import json
import urllib.error
import urllib.request
from typing import Any

# Open-Meteo answers in well under a second; past this the caller falls back to its cache.
TIMEOUT_S = 4.0
# Both answers are a few KB. Anything far bigger is not what we asked for.
MAX_BYTES = 512 * 1024
# ipapi.co refuses requests with no User-Agent.
USER_AGENT = "signal-weather/0.1"


class WeatherError(RuntimeError):
    """A lookup failed: network, HTTP status, size, or an answer that isn't the expected JSON."""


def get_json(url: str, timeout_s: float = TIMEOUT_S, max_bytes: int = MAX_BYTES) -> Any:
    """GET `url` and parse the body as JSON.

    Args:
        url: An https:// URL (anything else is refused).
        timeout_s: Connect and read timeout.
        max_bytes: Bodies longer than this are refused.

    Returns:
        The parsed JSON value.

    Raises:
        WeatherError: Not https, a network or HTTP error, an oversized body, or bad JSON.
    """
    if not url.startswith("https://"):
        raise WeatherError(f"refusing a non-https URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read(max_bytes + 1)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise WeatherError(f"GET {url.split('?')[0]} failed: {error}") from error
    if len(body) > max_bytes:
        raise WeatherError(f"GET {url.split('?')[0]}: answer over {max_bytes} bytes")
    try:
        return json.loads(body)
    except ValueError as error:
        raise WeatherError(f"GET {url.split('?')[0]}: not JSON ({error})") from error
