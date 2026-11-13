# whiteboard.display.screen

Find the projector, and put the board page fullscreen on it.

## Public API (`from whiteboard.display.screen import ...`)

- `list_monitors() -> list[Monitor]`, via ctypes `EnumDisplayMonitors` + `GetMonitorInfoW` in a per-monitor-DPI-aware thread context.
  - `Monitor` has `device_name` (`\\.\DISPLAY1`), `friendly_name` (EDID, e.g. `PROJ-1 TV`, from `QueryDisplayConfig`; `""` if unavailable), physical `x, y, width, height`, `is_primary` and `scale`.
  - `logical_size` is the CSS-pixel size of a fullscreen page on that monitor.
- `pick_projector(monitors, name_match)` / `find_projector(name_match)`: a case-insensitive substring of the friendly or device name, else the first non-primary display. Raises `ProjectorNotFoundError`.
- `launch_kiosk(url, monitor, profile_dir, edge_path="") -> KioskWindow` closes any kiosk already using `profile_dir`, then starts Edge. `KioskWindow.close()` closes it again: WM_CLOSE, then a forced kill after 5 s.
- `kiosk_command(...)`, `find_edge(...)`, `close_kiosk(profile_dir)`, `find_kiosk_browser_pids(profile_dir)`.

## Edge flags (verified on this machine)

`msedge.exe --kiosk <url> --edge-kiosk-type=fullscreen --window-position=<x/scale>,<y/scale> --window-size=<logical w>,<logical h> --user-data-dir=.state/edge-profile --no-first-run --no-default-browser-check --hide-crash-restore-bubble --disable-features=Translate`

- `--window-position` takes logical (DIP) coordinates: with both displays at 150%, the projector at physical X=1920 is `1280,0`. With those flags, the window lands on the projector's exact physical bounds, fullscreen, with no frame.
- Kiosk mode runs InPrivate, so nothing persists between runs.
- The started `msedge.exe` relaunches itself and exits. The kiosk is therefore found by the `--user-data-dir` in its command line (via PowerShell `Get-CimInstance`), not by the Popen handle.
- A graceful `taskkill /PID <browser>` without `/T` closes it cleanly. With `/T`, taskkill tries the children first, and they refuse.

## Dependencies

Standard library only (`ctypes`, `subprocess`). Windows 10+ (`SetThreadDpiAwarenessContext`, `GetDpiForMonitor`), and Edge.
