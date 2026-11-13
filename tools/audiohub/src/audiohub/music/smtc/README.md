# audiohub.music.smtc

The Windows media session (System Media Transport Controls) backend for `audiohub.music`. It needs no login, no Premium and no network, and it works with any app shown in the Windows media flyout.

## Public API

- `SmtcController(request_manager=request_session_manager)`
  - Supports play, pause, toggle, next, previous and `now_playing`.
  - Volume, search and queue raise `UnsupportedOperation`.
  - With no media session, commands raise `MusicUnavailable(NO_SESSION)`, and `now_playing()` returns None.
  - A failed winrt call (OSError from a failed HRESULT) raises `MusicUnavailable(REQUEST_FAILED)`.
  - Uses Spotify's session if there is one, otherwise the current session.

## Files

| File | Contents |
|---|---|
| `manager.py` | deferred winrt import, `request_session_manager()`, `winrt_errors_as_unavailable()`, session protocols |
| `sessions.py` | `pick_session`: Spotify first, else the current session |
| `controller.py` | `SmtcController` |

## Notes

- `get_sessions()` needs the `winrt-Windows.Foundation.Collections` projection, a pinned dependency. If it's ever missing, a warning is logged once and the current session is used instead of Spotify's.
- Commands that an app ignores (`try_*_async` resolving to False) raise `MusicUnavailable(REQUEST_FAILED)` naming the app.

## Dependencies

- `winrt-runtime`, `winrt-Windows.Foundation`, `winrt-Windows.Foundation.Collections`, `winrt-Windows.Media.Control`.
- The parent package's `errors`, `now_playing` and `controller` modules.
