"""signal_weather: the weather cache rule and the location fallback, with fake lookups."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from signal_weather import Place, Weather, WeatherError, current_weather, locate

SPRINGFIELD = Place("Springfield, IL", 39.7817, -89.6501)
NOON = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)


def reading_at(at: datetime, temp_f: int = 61) -> Weather:
    return Weather(temp_f, 64, 48, 10, 2, True, "Partly cloudy", at)


def failing(*_args: object) -> Weather:
    raise WeatherError("network down")


@pytest.mark.parametrize(
    ("cache_age", "expected_temp", "is_stale"),
    [
        (None, None, True),  # nothing cached: unavailable
        (timedelta(hours=2), 50, True),  # cached within 6 h: shown "as of"
        (timedelta(hours=7), None, True),  # cached past 6 h: unavailable
    ],
)
def test_failed_fetch_falls_back_to_a_cache_up_to_six_hours_old(
    tmp_path: Path, cache_age: timedelta | None, expected_temp: int | None, is_stale: bool
) -> None:
    cache = tmp_path / "weather.json"
    if cache_age is not None:
        # Seed the cache through a successful fetch at that time.
        current_weather(SPRINGFIELD, cache, NOON - cache_age, fetch=lambda _p, at: reading_at(at, 50))
    reading = current_weather(SPRINGFIELD, cache, NOON, fetch=failing)
    assert (reading.weather.temp_f if reading.weather else None) == expected_temp
    assert reading.is_stale is is_stale and reading.error == "network down"


def test_fresh_cache_is_used_without_fetching_and_a_new_place_fetches(tmp_path: Path) -> None:
    cache = tmp_path / "weather.json"
    first = current_weather(SPRINGFIELD, cache, NOON, fetch=lambda _p, at: reading_at(at))
    assert first.weather.temp_f == 61 and not first.is_stale
    # 10 minutes later: from the cache, so a failing fetch is never called.
    again = current_weather(SPRINGFIELD, cache, NOON + timedelta(minutes=10), fetch=failing)
    assert again.weather == first.weather and again.error is None
    # A different place never gets another place's reading, even as a fallback.
    chicago = Place("Chicago, IL", 41.88, -87.63)
    assert current_weather(chicago, cache, NOON, fetch=failing).weather is None


def test_locate_uses_the_lookup_then_the_last_place_then_the_fallback(tmp_path: Path) -> None:
    cache = tmp_path / "location.json"

    def lookup_fails() -> Place:
        raise WeatherError("rate limited")

    assert locate(cache, SPRINGFIELD, lookup_fails) == (SPRINGFIELD, "rate limited")
    chicago = Place("Chicago, IL", 41.88, -87.63)
    assert locate(cache, SPRINGFIELD, lambda: chicago) == (chicago, None)
    assert locate(cache, SPRINGFIELD, lookup_fails) == (chicago, "rate limited")
