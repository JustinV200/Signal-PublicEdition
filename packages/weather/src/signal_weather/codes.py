"""condition_word: the WMO weather_code Open-Meteo returns, as a short word.

The words are the idle board's (refdocs/research/idle-board/design.md section 5): each
is under 14 characters so it fits the board's words column. Clear and partly cloudy
read differently by day and night. The board always shows this word next to the glyph,
so it also works for colourblind users; the glyph is only a second cue.
"""

# (day word, night word) for the codes whose word depends on daylight.
_DAY_NIGHT = {0: ("Sunny", "Clear"), 1: ("Mostly sunny", "Mostly clear")}
_WORDS = {
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Fog",
    51: "Drizzle",
    53: "Drizzle",
    55: "Drizzle",
    56: "Icy drizzle",
    57: "Icy drizzle",
    61: "Rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Showers",
    81: "Showers",
    82: "Heavy showers",
    85: "Snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Hail storm",
    99: "Hail storm",
}
# Any code the table doesn't know: never a blank.
FALLBACK_WORD = "Cloudy"


def condition_word(code: int, is_day: bool) -> str:
    """The word for a WMO weather code.

    Args:
        code: Open-Meteo's `weather_code`.
        is_day: Open-Meteo's `is_day` (only changes codes 0 and 1).
    """
    if code in _DAY_NIGHT:
        day_word, night_word = _DAY_NIGHT[code]
        return day_word if is_day else night_word
    return _WORDS.get(code, FALLBACK_WORD)
