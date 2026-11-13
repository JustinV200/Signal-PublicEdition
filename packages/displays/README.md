# signal_displays (packages/displays)

Lists the attached monitors and picks the projector by name. Used by `tools/sleepmode`.

The code was lifted from `tools/whiteboard` (`whiteboard.display.screen.monitors` and `friendly_names`), which still has its own copy. TODO: switch the whiteboard to this package (an import swap; the API is the same plus `Monitor.handle`) the next time `whiteboard.display.screen` is touched, then delete its copy.

## Public API (`from signal_displays import ...`)

- `list_monitors() -> list[Monitor]` uses ctypes `EnumDisplayMonitors` + `GetMonitorInfoW` in a per-monitor-DPI-aware thread context.
  - `Monitor` has `device_name` (`\\.\DISPLAY1`), `friendly_name` (EDID, e.g. `PROJ-1 TV`, from `QueryDisplayConfig`; `""` if unavailable), physical `x, y, width, height`, `is_primary`, `scale` and `handle` (the HMONITOR, valid until the display layout changes).
  - `logical_size` is the CSS-pixel size of a fullscreen page on that monitor.
  - Raises `OSError` if enumeration fails. Friendly names are best-effort: a failure logs a warning and leaves them empty.
- `pick_projector(monitors, name_match)` / `find_projector(name_match)`: a case-insensitive substring of the friendly or device name, else the first non-primary display. Raises `ProjectorNotFoundError`.
- `friendly_names() -> dict[str, str]`: GDI device name to EDID friendly name.

## Depends on

The standard library only (`ctypes`). Windows 10+ (`SetThreadDpiAwarenessContext`, `GetDpiForMonitor`). Tools add it with `uv add --editable ../../packages/displays`.

## Tests

```
uv run pytest
```
