"""locate: this PC's approximate place, from a keyless IP lookup, with a cache and a fallback.

The lookup is ipapi.co's free HTTPS endpoint (no key, about 1000 lookups a day; callers
look up at start and every few hours). It sends nothing but the request itself; the
service sees the PC's public IP, which is the point. If it fails, the last place it
found is used, and if there's none, the caller's fallback (a fixed place in config).
"""

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from signal_jsonstate import StateFileError, read_json_object, write_json_atomic

from signal_weather.http import WeatherError, get_json

log = logging.getLogger(__name__)

LOOKUP_URL = "https://ipapi.co/json/"
MAX_LATITUDE = 90.0
MAX_LONGITUDE = 180.0
# Place names are shown on the board; anything longer is cut.
MAX_NAME_CHARS = 40


@dataclass(frozen=True)
class Place:
    """A named point on the map.

    Attributes:
        name: Short display name, e.g. "Springfield, IL".
        lat: Latitude in degrees.
        lon: Longitude in degrees.
    """

    name: str
    lat: float
    lon: float


def lookup_place() -> Place:
    """Ask the IP location service where this PC is.

    Raises:
        WeatherError: The lookup failed or its answer isn't a usable place.
    """
    return place_from_answer(get_json(LOOKUP_URL))


def place_from_answer(answer: Any) -> Place:
    """Validate ipapi.co's JSON into a Place.

    Raises:
        WeatherError: An error answer (e.g. rate limited), or a bad or missing field.
    """
    if not isinstance(answer, dict) or answer.get("error"):
        reason = answer.get("reason") if isinstance(answer, dict) else None
        raise WeatherError(f"location lookup refused: {reason or 'unexpected answer'}")
    lat = _coordinate(answer.get("latitude"), MAX_LATITUDE)
    lon = _coordinate(answer.get("longitude"), MAX_LONGITUDE)
    city = answer.get("city")
    if not isinstance(city, str) or not city.strip():
        raise WeatherError("location lookup gave no city")
    # US places read best with the state ("Springfield, IL"), others with the country.
    is_us = answer.get("country_code") == "US"
    area = answer.get("region_code") if is_us else answer.get("country_code")
    name = f"{city.strip()}, {area}" if isinstance(area, str) and area else city.strip()
    return Place(name[:MAX_NAME_CHARS], lat, lon)


def locate(
    cache_path: Path, fallback: Place, lookup: Callable[[], Place] = lookup_place
) -> tuple[Place, str | None]:
    """Where this PC is now: a fresh lookup, else the last one found, else `fallback`.

    Args:
        cache_path: The last place found (a small JSON file, written atomically).
        fallback: Used when the lookup fails and nothing is cached.
        lookup: Finds the place; tests pass a fake.

    Returns:
        (the place, why the lookup failed or None).
    """
    try:
        place = lookup()
    except WeatherError as error:
        return _cached_place(cache_path) or fallback, str(error)
    try:
        write_json_atomic(cache_path, {"name": place.name, "lat": place.lat, "lon": place.lon})
    except StateFileError as error:
        log.warning("can't cache the location in %s: %s", cache_path, error)
    return place, None


def _cached_place(cache_path: Path) -> Place | None:
    """The cached place, or None if there's none or it's unreadable."""
    try:
        data = read_json_object(cache_path)
        return Place(
            str(data["name"]),
            _coordinate(data["lat"], MAX_LATITUDE),
            _coordinate(data["lon"], MAX_LONGITUDE),
        )
    except (StateFileError, KeyError, WeatherError):
        return None


def _coordinate(value: Any, limit: float) -> float:
    """A finite number within +-limit.

    Raises:
        WeatherError: Anything else.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise WeatherError(f"bad coordinate {value!r}")
    if not math.isfinite(value) or abs(value) > limit:
        raise WeatherError(f"coordinate out of range: {value!r}")
    return float(value)
