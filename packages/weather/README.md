# signal_weather (packages/weather)

Keyless weather and the PC's approximate location, each behind a small JSON cache. The whiteboard's idle view shows it; the brief's morning brief is meant to reuse it (refdocs/research/brief-me.md section 8). Everything blocks (stdlib `urllib`), so async callers run it in a thread.

## Public API (`from signal_weather import ...`)

- `locate(cache_path, fallback, lookup=lookup_place) -> (Place, error | None)`: a fresh IP lookup (ipapi.co, HTTPS, keyless); if it fails, the last place it found (`cache_path`), else `fallback`. The caller decides how often (the whiteboard: at daemon start, then every 6 h).
- `current_weather(place, cache_path, now, fresh_for=30 min, fetch=fetch_forecast) -> Reading(weather, is_stale, error)`:
  - a cached reading for the same place (within about 1 km) younger than `fresh_for` is used without asking;
  - else Open-Meteo is asked (°F, `timezone=auto`, sends only the coordinates);
  - if that fails, a cached reading up to `STALE_LIMIT` (6 h) old comes back with `is_stale=True`;
  - past that, `weather` is None ("weather unavailable").
- `Weather(temp_f, high_f, low_f, rain_pct, code, is_day, word, fetched_at)`: rounded for display. `word` comes from `condition_word(code, is_day)`, the WMO code table in the idle board's design (every word under 14 characters).
- `Place(name, lat, lon)`, e.g. `Place("Springfield, IL", 39.7817, -89.6501)`.
- `fetch_forecast(place, now)`, `lookup_place()`: the raw lookups. Raise `WeatherError`.
- `WeatherError`: a lookup failed (network, HTTP, a body over 512 KB, a non-https URL, or an answer missing a field). Each GET has a 4 s timeout.

## Network

Two keyless HTTPS GETs: `api.open-meteo.com/v1/forecast` (coordinates only) and `ipapi.co/json/` (the service sees the PC's public IP, which is what it locates). No secrets.

## Depends on

`signal-jsonstate` (atomic JSON writes that create a missing cache folder, tolerant reads).

## Tests

`uv run --frozen pytest` (fake lookups, no network).
