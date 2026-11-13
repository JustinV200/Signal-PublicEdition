"""NetworkSources: the idle view's two network regions, weather and the news ticker.

- Weather: signal_weather, for the PC's place. With [idle] locate on, the place comes
  from an IP lookup on the first refresh after daemon start and every [idle] locate_hours;
  a failed lookup uses the last place found, else [idle] place/lat/lon. The forecast's
  own cache rule (fresh 30 min, stale fallback up to 6 h) lives in signal_weather.
- News: one https RSS 2.0 or Atom feed ([idle] news_feed), fetched with aiohttp, FETCH_TIMEOUT_S and
  a size cap, parsed by whiteboard.idle.parse_headlines. A failed fetch keeps the last
  headlines up to NEWS_KEEP, then shows none. Kept in memory only: a restarted daemon
  fetches again at once.
Failures never raise out of here; each outage is logged once (Outages).
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from signal_weather import (
    Place,
    Reading,
    Weather,
    current_weather,
    fetch_forecast,
    locate,
    lookup_place,
)

from whiteboard.config import IdleSettings
from whiteboard.daemon.idle.local_sources import IdleFiles
from whiteboard.daemon.idle.outages import Outages
from whiteboard.idle import MAX_FEED_BYTES, NewsError, parse_headlines

NEWS_KEEP = timedelta(hours=6)
FETCH_TIMEOUT_S = 4.0
HTTP_OK = 200
LOCATION_CACHE = "location.json"
WEATHER_CACHE = "weather.json"


async def fetch_feed(url: str) -> bytes:
    """GET an https feed, at most MAX_FEED_BYTES + 1 bytes of it (parse_headlines refuses more).

    Redirects aren't followed, so the feed can never be swapped for a plain-http or other
    host's page; a feed that moved is a config change ([idle] news_feed).

    Raises:
        NewsError: Not an https URL, or any answer but 200 (a redirect included).
        aiohttp.ClientError, TimeoutError: The request failed or took too long.
    """
    if not url.startswith("https://"):
        raise NewsError(f"refusing a non-https feed URL: {url}")
    timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT_S)
    async with (
        aiohttp.ClientSession(timeout=timeout) as session,
        session.get(url, allow_redirects=False) as response,
    ):
        if response.status != HTTP_OK:
            raise NewsError(f"feed answered HTTP {response.status}; expected 200 (no redirects)")
        body = bytearray()
        async for chunk in response.content.iter_chunked(64 * 1024):
            body += chunk
            if len(body) > MAX_FEED_BYTES:
                break
        return bytes(body)


@dataclass(frozen=True)
class Lookups:
    """The network calls, swappable in tests. Signatures as in signal_weather and fetch_feed."""

    place: Callable[[], Place] = lookup_place
    forecast: Callable[[Place, datetime], Weather] = fetch_forecast
    feed: Callable[[str], Awaitable[bytes]] = fetch_feed


class NetworkSources:
    """Weather and headlines for the idle view; see the module docstring."""

    def __init__(
        self,
        settings: IdleSettings,
        files: IdleFiles,
        outages: Outages,
        lookups: Lookups,
    ) -> None:
        """Args:
        settings: The [idle] section.
        files: Its cache_dir holds the weather and location caches.
        outages: Logs each source's outage once.
        lookups: The network calls (fakes in tests).
        """
        self._settings = settings
        self._files = files
        self._outages = outages
        self._lookups = lookups
        self._place = Place(settings.place, settings.lat, settings.lon)
        self._located_at: datetime | None = None
        self._news: dict[str, Any] | None = None
        self._news_at: datetime | None = None

    async def weather(self, now: datetime) -> dict[str, Any] | None:
        """The WEATHER region now, or None for "Weather unavailable".

        Args:
            now: Local time now (aware).
        """
        if self._settings.locate and (
            self._located_at is None
            or now - self._located_at >= timedelta(hours=self._settings.locate_hours)
        ):
            self._located_at = now
            await asyncio.to_thread(self._locate)
        fresh_for = timedelta(minutes=self._settings.weather_min)
        reading = await asyncio.to_thread(
            current_weather,
            self._place,
            self._files.cache_dir / WEATHER_CACHE,
            now,
            fresh_for,
            self._lookups.forecast,
        )
        if reading.error:
            self._outages.failed("weather", reading.error)
        else:
            self._outages.ok("weather")
        return _weather_region(reading, self._place)

    async def news(self, now: datetime) -> dict[str, Any] | None:
        """The NEWS ticker now (`{headlines, source, px_s}`), or None for "No headline".

        Args:
            now: The current time (aware).
        """
        try:
            body = await self._lookups.feed(self._settings.news_feed)
            headlines = parse_headlines(body, now)
        except (NewsError, aiohttp.ClientError, TimeoutError) as error:
            self._outages.failed("news feed", error)
            if self._news_at is not None and now - self._news_at > NEWS_KEEP:
                self._news = None
            return self._news
        self._outages.ok("news feed")
        self._news_at = now
        settings = self._settings
        self._news = (
            {"headlines": headlines, "source": settings.news_source, "px_s": settings.ticker_px_s}
            if headlines
            else None
        )
        return self._news

    def _locate(self) -> None:
        """Look the place up (worker thread); a failure keeps the cached or configured place."""
        fallback = Place(self._settings.place, self._settings.lat, self._settings.lon)
        self._place, error = locate(
            self._files.cache_dir / LOCATION_CACHE, fallback, self._lookups.place
        )
        if error:
            self._outages.failed("location lookup", error)
        else:
            self._outages.ok("location lookup")


def _weather_region(reading: Reading, place: Place) -> dict[str, Any] | None:
    """The page's weather data; `as_of` (local HH:MM) only on a stale reading."""
    weather = reading.weather
    if weather is None:
        return None
    as_of = f"{weather.fetched_at.astimezone():%H:%M}" if reading.is_stale else None
    return {
        "code": weather.code,
        "is_day": weather.is_day,
        "temp": weather.temp_f,
        "hi": weather.high_f,
        "lo": weather.low_f,
        "rain": weather.rain_pct,
        "word": weather.word,
        "place": place.name,
        "as_of": as_of,
    }
