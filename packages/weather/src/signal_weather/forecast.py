"""current_weather: today's weather for a place, from Open-Meteo, behind a small file cache.

The cache rule (refdocs/research/idle-board/plan.md and brief-me.md section 8):
- a cached reading for the same place younger than `fresh_for` is used as it is;
- otherwise Open-Meteo is asked (keyless, sends only the coordinates);
- if that fails, a cached reading up to STALE_LIMIT old is used, marked stale ("as of");
- past that there's no weather, and the caller says "weather unavailable".
Blocking (urllib): async callers run it in a thread.
"""

import logging
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from signal_jsonstate import StateFileError, read_json_object, write_json_atomic

from signal_weather.codes import condition_word
from signal_weather.http import WeatherError, get_json
from signal_weather.location import Place

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_FRESH_FOR = timedelta(minutes=30)
STALE_LIMIT = timedelta(hours=6)
# Cached readings for a point further than this (degrees, about 1 km) are another place's.
SAME_PLACE_DEGREES = 0.01


@dataclass(frozen=True)
class Weather:
    """One reading, rounded for display.

    Attributes:
        temp_f: Now, in degrees Fahrenheit.
        high_f, low_f: Today's high and low.
        rain_pct: Today's highest chance of rain, 0-100.
        code: The current WMO weather code.
        is_day: Whether it's daytime there now.
        word: The condition word (codes.condition_word).
        fetched_at: When Open-Meteo answered (aware).
    """

    temp_f: int
    high_f: int
    low_f: int
    rain_pct: int
    code: int
    is_day: bool
    word: str
    fetched_at: datetime


@dataclass(frozen=True)
class Reading:
    """What current_weather found.

    Attributes:
        weather: The reading, or None when there's none to show.
        is_stale: True when the fetch failed and this is an older cached reading.
        error: Why the fetch failed, or None (no fetch, or it worked).
    """

    weather: Weather | None
    is_stale: bool
    error: str | None


def fetch_forecast(place: Place, now: datetime) -> Weather:
    """Ask Open-Meteo for the place's weather now and today's range.

    Raises:
        WeatherError: The request failed or the answer is missing a field.
    """
    query = urlencode(
        {
            "latitude": f"{place.lat:.4f}",
            "longitude": f"{place.lon:.4f}",
            "current": "temperature_2m,weather_code,is_day",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "temperature_unit": "fahrenheit",
            # The place's own time zone, so "today" is the place's day.
            "timezone": "auto",
            "forecast_days": 1,
        }
    )
    return weather_from_answer(get_json(f"{FORECAST_URL}?{query}"), now)


def weather_from_answer(answer: Any, now: datetime) -> Weather:
    """Validate Open-Meteo's JSON into a Weather.

    Raises:
        WeatherError: A field is missing or isn't a finite number.
    """
    try:
        current, daily = answer["current"], answer["daily"]
        code = int(_number(current["weather_code"]))
        is_day = bool(_number(current["is_day"]))
        return Weather(
            temp_f=round(_number(current["temperature_2m"])),
            high_f=round(_number(daily["temperature_2m_max"][0])),
            low_f=round(_number(daily["temperature_2m_min"][0])),
            # Open-Meteo leaves this null where it has no model for it.
            rain_pct=round(_number(daily["precipitation_probability_max"][0] or 0)),
            code=code,
            is_day=is_day,
            word=condition_word(code, is_day),
            fetched_at=now,
        )
    except (KeyError, IndexError, TypeError) as error:
        raise WeatherError(f"unexpected forecast answer: {error!r}") from error


def current_weather(
    place: Place,
    cache_path: Path,
    now: datetime,
    fresh_for: timedelta = DEFAULT_FRESH_FOR,
    fetch: Callable[[Place, datetime], Weather] = fetch_forecast,
) -> Reading:
    """The weather to show now, following the cache rule in the module docstring.

    Args:
        place: Where.
        cache_path: The last good reading (JSON, written atomically).
        now: The current time (aware).
        fresh_for: How long a cached reading is used without asking again.
        fetch: Asks Open-Meteo; tests pass a fake.
    """
    cached = _cached_weather(cache_path, place)
    if cached is not None and now - cached.fetched_at < fresh_for:
        return Reading(cached, False, None)
    try:
        weather = fetch(place, now)
    except WeatherError as error:
        if cached is not None and now - cached.fetched_at <= STALE_LIMIT:
            return Reading(cached, True, str(error))
        return Reading(None, True, str(error))
    _write_cache(cache_path, place, weather)
    return Reading(weather, False, None)


def _cached_weather(cache_path: Path, place: Place) -> Weather | None:
    """The cached reading if it's for this place and readable, else None."""
    try:
        data = read_json_object(cache_path)
        if abs(data["lat"] - place.lat) > SAME_PLACE_DEGREES:
            return None
        if abs(data["lon"] - place.lon) > SAME_PLACE_DEGREES:
            return None
        fields = data["weather"]
        return Weather(**{**fields, "fetched_at": datetime.fromisoformat(fields["fetched_at"])})
    except (StateFileError, KeyError, TypeError, ValueError):
        return None


def _write_cache(cache_path: Path, place: Place, weather: Weather) -> None:
    """Keep the reading; a failed write only costs the fallback, so it's logged."""
    fields = {**asdict(weather), "fetched_at": weather.fetched_at.isoformat()}
    try:
        write_json_atomic(cache_path, {"lat": place.lat, "lon": place.lon, "weather": fields})
    except StateFileError as error:
        log.warning("can't cache the weather in %s: %s", cache_path, error)


def _number(value: Any) -> float:
    """A finite int or float.

    Raises:
        WeatherError: Anything else (bool and null included).
    """
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise WeatherError(f"bad number in forecast: {value!r}")
    return float(value)
