# whiteboard.daemon.kiosk

The board page's Edge kiosk on the projector, inside the running daemon: open it, keep it open, close it.

## Public API

- `find_projector_monitor(display) -> Monitor | None` and `projector_size(monitor)`: the projector (`[display] name_match`), and the stage size (its logical pixels, else 1280x720).
- `build_kiosk(display, monitor, state_dir, token) -> Kiosk | None`: None (and a log line on opening the page by hand) without a projector or with `[display] launch_kiosk = false`. `Kiosk.open()` starts Edge (closing a stale kiosk on the same profile first); `Kiosk.close()` closes it.
- `KioskWatchdog(kiosk, page_count, clock=time.monotonic, sleep=time.sleep)`:
  - `check()` reopens the kiosk when no board page is connected, unless it's backing off. After the start-up open it waits 5 s and checks again first, so a page reloading or reconnecting isn't killed. Each reopen that no page follows doubles the wait before the next (30 s, 60 s, 2, 4, 8, then 16 minutes); a connected page resets it. Every try and failure is logged. Never raises.
  - `start(stack)` checks at once (the first open), then every 30 s, day and night, until the daemon's exit stack unwinds. It stops before the kiosk closes, so a shutdown never reopens it.
  - `stop()` waits out a reopen in flight; every later `check()` is a no-op.
- `add_kiosk_routes(app, watchdog | None)`: `POST /api/kiosk/open` runs `check()` now and answers `{ok, opened}` (opened is false while a page is connected or it's backing off); 409 when the kiosk is off or the watchdog has stopped. It's under `/api/`, so it needs the daemon token like every other route. Sleep mode's night guard calls it when the daemon is up but nothing shows the night view.

Why a page and not the Edge process: the page is what the projector shows, so an Edge left on an error page counts as gone too, and checking needs no PowerShell every 30 s. The board page reconnects within a second (`board.js`), well inside the 5 s re-check.

## Depends on

`whiteboard.config` (`DisplaySettings`), `whiteboard.display.screen` (`launch_kiosk`, `close_kiosk`, `find_projector`), `aiohttp`.
