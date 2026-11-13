# sleepmode.lighting

Turns the PC's RGB lights off at sleep and back on at wake, with no brand built in. Devices are found at run time, and a backend with nothing to reach logs why at INFO and is skipped.

## Backends, in order

Each meets the `Backend` protocol in `backend.py` (`name`, `off(may_snapshot, guard)`, `restore(guard)`).

1. **OpenRGB** (`openrgb_backend.py`, `openrgb_server.py`, `openrgb_cli.py`), for the most brands. It talks to OpenRGB's SDK server on 127.0.0.1:6742 through `openrgb-python`.
   - **No server running:** it starts `OpenRGB.exe --server --startminimized` through a console-less `cmd.exe` (OpenRGB attaches to its parent's console otherwise). It waits until the port answers and the device count holds for 2 s, up to 20 s.
   - **No server and no `OpenRGB.exe`:** it's skipped.
   - **The path to `OpenRGB.exe` is always quoted** for `cmd.exe`, so a `&` in a folder name is safe. A `%` isn't (`cmd.exe` expands it even in quotes), so such a path is refused with a note.
   - **A server sleepmode starts stays running.** OpenRGB can't read some devices' colours back, so the server's memory of what it set is the only record of the lights. The tray icon opens its window.
   - **Sleep:** each device goes to its "Off" mode, or Direct with every LED black. Nothing is saved to a device's own memory, and USB power is never touched.
   - **Wake:** it loads the `day` profile, else `sleepmode-before`.
   - **The `sleepmode-before` snapshot is saved only when there's no `day` profile** (wake would never use it otherwise). It's skipped when this sleep replaces one that already darkened the lights, or when every device already looks off. A freshly started OpenRGB reports "Direct, black" for devices it can't read, and a snapshot of that would bring nothing back.
   - **OpenRGB 1.0 quirks:**
     - Its server lets only its own protocol-6 "local client" save profiles, and `openrgb-python` speaks protocol 4 at most. So the snapshot is saved by running `OpenRGB.exe -sp sleepmode-before` (the CLI connects to the running server itself; adding `--client` makes it save every device twice).
     - After a profile save, the server sends SDK clients a notice `openrgb-python` can't parse. The session therefore closes its connection before the CLI save and reconnects after.
     - The client uses protocol 3, because the 1.0 server can leave protocol 4's plugin-list request unanswered (a 10 s stall).
2. **Windows Dynamic Lighting** (`lamparray.py`): a stub that reports no LampArray devices. Its TODO explains the catch: an unpackaged process only gets the lamps while it's in the foreground, so background control needs a sparse package.
3. **Vendor commands** (`commands.py`): `[lighting] off_commands` and `restore_commands` from `sleepmode.toml`, each an argv list run with no shell, no window and a 10 s timeout.

## Public API

- `Lighting(config_path, open_session=open_openrgb, run=run_command, step_timeout_s=LIGHTING_STEP_TIMEOUT_S)`:
  - `off(may_snapshot) -> LightingReport` and `restore() -> LightingReport`. Neither ever raises.
  - It reads `sleepmode.toml` on every call: `enabled = false` leaves the lights alone. A malformed file becomes a note: sleep then leaves the lights alone, and wake brings them back with the defaults (OpenRGB at its default path, loading `day`), since lights left dark all day are the worse mistake.
  - Each backend runs on a daemon thread with its own deadline (`run_with_deadline`, 45 s: OpenRGB's server start plus a snapshot save, with slack), so a hung server or tool can't hold up sleep or wake. An error or overrun becomes a note.
  - A thread can't be ended, so an overrun abandons the backend's `StepGuard` (`step_guard.py`). That closes its OpenRGB socket (an `openrgb-python` read can otherwise spin for good on a socket the server closed), and the backend checks the guard before each device change or command, so an abandoned sleep can't turn lights off after a later wake. A call stuck inside `OpenRGBClient()` itself has no socket to close yet, so it runs on until the process ends.
- `LightingReport(lines, notes)`: `lines` (one per backend that acted) go in the sleep summary, and `notes` are problems for the owner.
- `open_openrgb(exe_path) -> OpenRgbSession | None`, `OpenRgbSession(client, started_server, save_with_cli)` and `OpenOpenRgb`: the OpenRGB connection, which tests replace with a fake server.

## Depends on

`sleepmode.config` (timeouts, profile names, `load_lighting_settings`), `sleepmode.shared` (`popen_detached`), `openrgb-python` and the standard library.
