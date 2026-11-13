"""Public API of signal_weather: keyless weather and approximate location, with file caches.

The whiteboard's idle view shows it now; the brief's morning brief is meant to reuse it.
Everything here blocks (urllib), so async callers run it in a thread.
"""

from signal_weather.codes import condition_word
from signal_weather.forecast import (
    STALE_LIMIT,
    Reading,
    Weather,
    current_weather,
    fetch_forecast,
)
from signal_weather.http import WeatherError
from signal_weather.location import Place, locate, lookup_place

__all__ = [
    "STALE_LIMIT",
    "Place",
    "Reading",
    "Weather",
    "WeatherError",
    "condition_word",
    "current_weather",
    "fetch_forecast",
    "locate",
    "lookup_place",
]
