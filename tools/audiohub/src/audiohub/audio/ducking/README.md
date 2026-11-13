# audiohub.audio.ducking

Lowers other apps' Windows per-session volume (default `Spotify.exe`) while Claude speaks, then puts it back exactly. It's a subpackage of `audiohub.audio`, which re-exports its API.

## Public API

- `Ducker(ducking_settings, state_path=DUCKING_STATE_PATH)`
  - `duck()` and `restore()` fade the target sessions down to `level` times their volume and back.
  - `ducked()` wraps both in a context manager and restores even when the body raises.
  - Neither ever raises. Both block for about `fade_ms`.
  - duck() and restore() share a lock, so they're safe from executor threads, and a restore never overtakes a duck that's still fading.
  - Everything is keyed by app id: the session identifier, which has no process id, so it still matches after Spotify restarts.
  - `duck()` captures one original per app (the loudest of its sessions) and fades all of that app's sessions to `original * level`.
  - `restore()` sets every current session of each captured app back to its original, whatever its level or session instance.
  - Apps that have no session at restore time, or whose volume couldn't be set, become leftovers in `tools/audiohub/.cache/ducking.json`, because Windows brings a restarted app back at its ducked level.
  - Leftovers are recovered when a `Ducker` is created (after a crash) and at the start of each duck. A session is only put back while it's still at the saved ducked level, so a volume the user changed is left alone.
- `list_session_process_names()`: diagnostic list of the processes that have audio sessions.

## Files

| File | Contents |
|---|---|
| `ducker.py` | `Ducker`: locking, capture, restore, leftover recovery |
| `fade.py` | linear multi-session fades |
| `saved_volumes.py` | the crash-safety state file |
| `sessions.py` | pycaw session lookup on every active render endpoint, plus per-thread COM init |

## Dependencies

- Libraries: `pycaw`, `comtypes`, `psutil`.
- Inside audiohub: `audiohub.config` (`DuckingSettings`, `CACHE_DIR`).
