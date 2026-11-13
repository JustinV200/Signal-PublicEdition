# audiohub.music.spotify

The Spotify Web API backend for `audiohub.music`, built on spotipy with PKCE auth. See the parent README for setup.

## Public API

- `SpotifyController(music_settings, *, auth=None, api=None)`: the `MusicController` implementation, plus `check_ready()` and `login()`.
  - Player commands that fail with no active device are retried once on a device from `GET /me/player/devices`, preferring the device named like this PC's hostname, then any "Computer", then the first. Playback is transferred to it before the command is resent. That wakes an open but idle Spotify app.
  - `toggle()` reads `is_playing` from the playback state, so it also works for episodes and ads.
  - `play_liked(shuffle)` reads the user id from `GET /me` and starts the context `spotify:user:<id>:collection`, setting shuffle first when asked.
- `SpotifyAuth(music_settings, *, environ=None, cache_path=TOKEN_CACHE_PATH)`:
  - `check_ready()` makes no network call.
  - `access_token()` may refresh the token.
  - `login()` runs the interactive login.
- `CLIENT_ID_ENV_VAR`, `SCOPES`, `TOKEN_CACHE_PATH`, `SEARCH_LIMIT`.

## Files

| File | Contents |
|---|---|
| `auth.py` | client ID, PKCE auth manager, token cache, login |
| `client.py` | executor-backed `SpotifyCaller`, the real spotipy client |
| `errors.py` | spotipy HTTP error to `MusicUnavailable` mapping and its log line (DEBUG for an expected refusal), and the filter that drops spotipy's own ERROR line for that refusal |
| `messages.py` | every speakable Spotify failure message |
| `items.py` | artist names, item descriptions, search matches, the Liked Songs URI |
| `devices.py` | picks an idle device to wake |
| `playback.py` | playback state to `NowPlaying` |
| `controller.py` | `SpotifyController` |

## Dependencies

- `spotipy`.
- `audiohub.config`.
- The parent package's `errors`, `now_playing`, `controller` and `arguments` modules.
