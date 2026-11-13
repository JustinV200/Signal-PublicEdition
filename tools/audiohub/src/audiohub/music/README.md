# audiohub.music

Music control for audiohub, through the Spotify Web API (spotipy, PKCE login) or the Windows media session (SMTC, via winrt). The CLI, the MCP tools and the voice loop all use the same `MusicController` protocol. Background research: `refdocs/research/spotify-mcp.md`.

## Public API (`from audiohub.music import ...`)

- `MusicController` protocol. All methods are async:
  - `play()`, `pause()`, `toggle()`, `next()`, `previous()`
  - `now_playing() -> NowPlaying | None`
  - `set_volume(percent)`
  - `search_and_play(query, kind="track") -> str`, which returns a speakable description of what started
  - `queue(query) -> str`
  - `play_liked(shuffle=None) -> str` plays the user's Liked Songs (saved tracks). Search can't do this: Liked Songs isn't a playlist, and searching "liked songs" finds strangers' playlists with that name. Spotify plays the context `spotify:user:<id>:collection`, with the id from `GET /me`, so no library scope is needed. `shuffle` True/False sets shuffle first; None leaves it.
- `NowPlaying(title, artist, album, is_playing, source)`
  - `source` is `"spotify"` for the Web API, or `"smtc:<app id>"`, e.g. `smtc:Spotify.exe` or `smtc:MSEdge`.
  - `describe()` returns e.g. "Babydoll by Dominic Fike".
- Errors. `str(error)` is always a sentence that can be spoken as is.
  - `MusicUnavailable(message, reason)`: the backend can't do it right now. `reason` is an `UnavailableReason`, e.g. `NOT_CONFIGURED`, `NOT_LOGGED_IN`, `NO_ACTIVE_DEVICE`, `PREMIUM_REQUIRED`, `RATE_LIMITED`, `NOT_FOUND`, `RESTRICTED`, `NO_SESSION`.
  - `UnsupportedOperation(message)`: the backend can never do it.
  - `ValueError`: a bad argument (volume outside 0-100, a blank query, an unknown kind).
- Backends:
  - `SpotifyController(music_settings)`. Also has `check_ready()` (no network) and `login()` (the interactive browser login, blocking).
  - `SmtcController()`: play/pause/toggle/next/previous/now_playing. Volume, search, Liked Songs and queue raise `UnsupportedOperation`.
  - `FallbackController(primary, fallback)`: transport controls drop to the fallback when the primary raises a reason in `FALLBACK_REASONS`: not configured, not logged in, or no active device. Premium-required is reported, not hidden by the fallback, so pause and now-playing always read the same backend. Volume, search, Liked Songs and queue use the primary only, so they report the primary's error.
- `create_controller(music_settings)` builds one of the three from `[music] backend`: `AUTO_BACKEND` (Fallback of Spotify then SMTC), `SPOTIFY_BACKEND` or `SMTC_BACKEND`.
- Argument checks: `check_volume_percent`, `check_query`, `check_search_kind`, `SEARCH_KINDS`, `MIN_VOLUME_PERCENT`, `MAX_VOLUME_PERCENT`.
- `CLIENT_ID_ENV_VAR` (`SPOTIPY_CLIENT_ID`) and `TOKEN_CACHE_PATH` (`tools/audiohub/.cache/spotify-token.json`, gitignored).

## Spotify setup

1. You need Premium, on the account that owns the developer app.
2. Create a Web API app at https://developer.spotify.com/dashboard.
3. Register the redirect URI `http://127.0.0.1:8888/callback` exactly. Spotify rejects `localhost`.
4. Set the user environment variable `SPOTIPY_CLIENT_ID` to the app's client ID. PKCE needs no client secret.
5. Run `uv run audiohub music login` once. The token is cached and refreshes itself.
6. Keep the Spotify app open. If it's open but idle (no active device), player commands are retried on it, on the device named like this PC (hostname), else any "Computer", else the first listed. The device is made active (transfer playback) first, which wakes it.

Only `login()` ever starts spotipy's interactive login. Every other call raises `MusicUnavailable` when there's no token, so the hub and the MCP server never block on a browser or a stdin prompt.

## Notes

- `pause()` is idempotent: music already paused counts as paused. The hub pauses the music itself while the user talks with Claude, so a spoken "pause the music" would otherwise report a failure.
  - Spotify always gets the pause. Its refusal for a paused player ("Restriction violated", `RESTRICTED`) counts as success once the playback state reads paused. A lost device still goes through the idle-device path first.
  - SMTC sends nothing when the session is paused or stopped. Any other status, such as mid track change, still gets the pause.
- `pause()` confirms: Spotify (via the playback state) and SMTC (via the session status) are re-read up to 3 times, and a pause that was accepted but left the music playing raises `MusicUnavailable` instead of reporting success.
- Music the hub paused for a conversation is just paused to the player, so `now_playing()` (and the `music_now_playing` tool) reports it as paused ("Paused: ...").
- Every Spotify HTTP error is logged at WARNING (status, reason, short body, never a token) by `spotify/errors.py`. The one exception is pause's expected refusal: it is logged once, at DEBUG, there; spotipy's own ERROR line for it is dropped. The controller warns only if the music is still playing.
- spotipy calls run in the default executor, one at a time, sharing one client.
- Status retries are off: urllib3 would honour a Retry-After of up to 6 hours. A 429 is reported straight away as `RATE_LIMITED`.
- Search uses `limit=5`. Dev-mode apps are capped at 10 results.
- SMTC prefers Spotify's media session and otherwise uses the current one. winrt failures (OSError) become `MusicUnavailable(REQUEST_FAILED)`.

## Layout

| Path | Contents |
|---|---|
| `controller.py` | `MusicController` protocol, `SearchKind` |
| `now_playing.py` | `NowPlaying` |
| `errors.py` | `MusicUnavailable`, `UnavailableReason`, `UnsupportedOperation` |
| `arguments.py` | argument checks |
| `fallback.py` | `FallbackController` |
| `factory.py` | `create_controller` |
| `spotify/` | Spotify Web API backend (see its README) |
| `smtc/` | Windows media session backend (see its README) |

## Dependencies

- Libraries: `spotipy`, `winrt-runtime`, `winrt-Windows.Foundation`, `winrt-Windows.Foundation.Collections`, `winrt-Windows.Media.Control`.
- Inside audiohub: only `audiohub.config` (`MusicSettings`, `MUSIC_BACKENDS`, `CACHE_DIR`).
