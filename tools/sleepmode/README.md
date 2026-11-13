# sleepmode

Sleep mode for the screens. It turns every monitor off (or black), puts a dim night sky on the whiteboard projector, turns the RGB lights off, and keeps the PC awake so agents keep running. The screens and lights come back at a set time, when you ask ("good morning"), or when you use the keyboard or mouse.

It never puts the PC to sleep, hibernates it or logs off, and it doesn't change the power plan. No admin rights needed. Windows 11, Python 3.12, uv.

## Setup

1. `cd tools/sleepmode && uv sync`.
2. The MCP server is registered in the repo's `.mcp.json` as `sleepmode`. Reconnect MCP (`/mcp`) in open sessions to get the tools.
3. Voice: the voice brain runs every tool of the servers in audiohub's `[brain] auto_allow_mcp_servers` without asking, and that list already includes `"sleepmode"`. If your `tools/audiohub/audiohub.toml` sets its own list, keep `"sleepmode"` in it.
4. RGB lights (optional): install OpenRGB (portable, at `%LOCALAPPDATA%\Programs\OpenRGB\OpenRGB.exe`) and save the daytime look as an OpenRGB profile named `day`. Without OpenRGB, the lights are left alone.
5. Per-machine options go in `sleepmode.toml` (gitignored; copy `sleepmode.example.toml`): `[lighting] enabled`, `openrgb_path`, and vendor `off_commands`/`restore_commands`; `[input] mouse_move_px` and `mouse_move_window_s` (how far the mouse must move to wake it).

## Commands

```
uv run --project tools/sleepmode sleepmode sleep [--wake 07:00] [--no-sky]
uv run --project tools/sleepmode sleepmode wake
uv run --project tools/sleepmode sleepmode status
```

- `--wake` takes `07:00`, `7`, `7am`, `6:30 pm`, or an ISO date-time like `2026-10-20T07:00`. A clock time means the next time it comes round.
- Running `sleep` while asleep updates the sleep. Without `--wake`, the wake time already set is kept. That only holds through MCP or voice ("turn off the night sky" keeps the 07:00 wake): typing `sleep --no-sky` is keyboard input, which wakes sleep mode first, so the new sleep starts with no wake time.
- `wake` is safe to run any time, as often as you like.

## MCP tools (`mcp__sleepmode__*`)

| Tool | For |
|---|---|
| `sleep_mode_on(wake_at="", night_sky=true)` | "sleep mode", "sleep mode until 7", "turn off the night sky" |
| `sleep_mode_off()` | "good morning", "sleep mode off" |
| `sleep_mode_status()` | "is sleep mode on?" |

Details are in `src/sleepmode/mcp_server/README.md`.

## What sleep does

1. **Finds the projector** the same way the whiteboard does. That's the whiteboard's `[display] name_match` (default `PROJ-1`), else the first non-primary display. The projector stays on.
2. **Sets the wake task** (`Signal sleep mode wake`) if there's a wake time. It's a one-shot, per-user scheduled task that runs `wake` and replaces any earlier one. It's set before any screen goes dark, so a `schtasks` that hangs leaves them lit.
3. **Turns the RGB lights off** (`sleepmode.lighting`), backends in order:
   - **OpenRGB** puts every device it lists in its "Off" mode (or black). If its SDK server isn't running, sleep starts it (`OpenRGB.exe --server --startminimized`, in the tray) and leaves it running, since the server is OpenRGB's only memory of the lights. With no `day` profile it first saves the look as `sleepmode-before`.
   - **Windows Dynamic Lighting** is a stub for now (no LampArray devices here).
   - **Your `off_commands`** come last.
   - It never powers off a USB port, and never saves to a device's own memory. Each backend gets 45 s (enough for OpenRGB to start and save a snapshot). One that overruns is abandoned and changes nothing after that, and a failure is a note, never an error.
   - This also comes before any screen goes dark, so a lighting step that hangs leaves them lit. It's before the keeper starts, too, so an input wake can't bring the lights back while they're still going off.
4. **Turns every other monitor off** with DDC/CI (VCP 0xD6 = 4, "DPM off", through dxva2). After 2 s it reads the power mode back. DDC/CI writes get no reply, so only a monitor that reads back an off mode (2 to 5) counts as off. One that refuses the write, switches itself back on, reads back anything else, or can't be read back gets a borderless, topmost black window with no mouse pointer instead. Over a monitor that did go off, the black window is invisible.
5. **Asks the whiteboard for the night view**: a night sky, or black with `--no-sky` (see the contract below). The whiteboard daemon serves it. If the daemon isn't running, or is an older one without the night view, the projector gets a black window too, and the keeper keeps trying (below). A daemon that isn't running (no `daemon.json` with a live pid) gets started in the background (`uv run --project tools/whiteboard --frozen whiteboard serve`, logging to the whiteboard's `.state/daemon.log`); sleep doesn't wait for it. Once up, it opens on the night view by itself, since sleep mode is on. A start that fails is a note in the sleep result, never a failed sleep. Wake never starts it.
6. **Starts the keeper**, a small background process. It has to still be running 2 s later, or the sleep counts as failed. It holds `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)`, plus `ES_DISPLAY_REQUIRED` whenever there's a projector, so the display timeout can't switch it off. It also draws the black windows, keeps the projector dark (every 60 s it checks `GET /api/status`: if the night view isn't on a connected page it covers the projector with a black window, then asks for the night view again and uncovers it once it shows, so a whiteboard started later still gets the sky) and wakes everything on real keyboard or mouse use (media, volume, browser and launch keys don't count, nor does a few pixels of mouse jitter), after a 5 s grace period. If the keeper itself fails, it wakes everything rather than leave the screens dark.
7. **Records it all** in `.state/state.json`. The new sleep's session id goes in first, before step 2, so the keeper of an earlier sleep exits instead of waking this one. An earlier keeper that hangs on is ended once the new one is up. The log is `.state/sleepmode.log`.

If any step after the session id is recorded fails (or you press Ctrl+C), sleep wakes everything back up, ends its own keeper (if it started) and an earlier keeper if they hang on, and reports the error, so the screens are never left dark without a keeper, and no keeper is left up that no state names.

`wake` undoes every step, even if the state file is missing:

- it sends DDC power-on to every monitor but the projector the sleep recorded, so a monitor that went off over DDC always gets its power-on, even if the display list looks different now;
- it tells the whiteboard to leave the night view;
- it marks the state awake, so the keeper closes its black windows, releases the keep-awake and exits;
- it brings the lights back: OpenRGB loads the `day` profile (else `sleepmode-before`), then your `restore_commands` run. A repeat wake leaves them be. If `sleepmode.toml` can't be read, wake still brings them back with the defaults (OpenRGB at its default path), and says so;
- it removes the wake task (only now, so a hung `schtasks` can't keep the black windows up);
- a keeper still running 5 s later is ended (that pid only, and only while its start time matches the recorded one, so a reused pid is left alone). This happens even if the state couldn't be marked awake, or Ctrl+C lands while `schtasks` runs.

## The whiteboard contract

The night view itself belongs to `tools/whiteboard`, whose daemon serves it. sleepmode only calls it, through the whiteboard daemon's existing authenticated loopback API:

- **Address and auth:** `http://127.0.0.1:<port>`, with the port from `tools/whiteboard/.state/daemon.json`. Each request carries `X-Signal-Token: <tools/whiteboard/.state/token>` and a JSON body, behind the daemon's usual request guard.
- **Never starting it:** sleepmode never starts the daemon. When it's not running, or answers 404 because it's an older daemon without the night routes, sleepmode logs it and uses a black window on the projector instead. A `daemon.json` whose `pid` has exited counts as not running straight away. The keeper retries the night view every 60 s.

### `POST /api/night/show`

Body: `{"seed": 20261019, "sky": true}`

- `seed` (int) is `YYYYMMDD` of the evening the night began; nights run noon to noon. The sky should be a pure function of the seed: a new sky each night, the same sky if it's shown twice in one night.
- `sky` (bool): `true` shows the night sky, `false` a plain black page.
- The daemon switches the scene's view to `"night"`, a new value next to `"items"` and `"todo"`. It remembers the view that was showing, unless it's already in the night view (then it keeps the remembered one), and saves both in `scene.json` so a daemon restart stays in the night view.
- The reply is `{"ok": true, "view": "night", "previous_view": "items"}`. sleepmode only checks `"ok": true`.

### `POST /api/night/hide`

Body: `{}`

- It goes back to the remembered view and replies `{"ok": true, "view": "items"}` (or `"todo"`).
- Outside the night view it changes nothing and still replies `ok`, because `wake` calls it every time.

### While the night view shows (whiteboard side)

- **Dim:** a black background with faint stars, and nothing large or bright, since the projector lights the room. Keep peak brightness low, about 25% grey.
- **Cheap:** slow CSS or canvas animation at a low frame rate, so it can run all night.
- **Different every night**, from a seeded random generator: star field, a constellation or two, the moon phase for the date, the odd shooting star.
- **Nothing that flashes or wakes things:** pause the change watcher and board agent, the automatic re-align checks and marker flashes, and anything else that projects bright patterns.
- `GET /api/status` reports `"view": "night"`.

## Known limits

- **Some displays don't speak DDC/CI.** A get-only probe on one setup found:
  - **A desktop monitor:** every VCP read fails with `0xC0262589` (`ERROR_GRAPHICS_DDCCI_INVALID_MESSAGE_COMMAND`), so sleepmode can't confirm a power-off and always gives it a black window. That's dark, but unless it did take the power-off, its backlight stays on. If its on-screen menu has a DDC/CI setting, turning it on may let sleepmode power it off and confirm it.
  - **PROJ-1 projector:** fails at the I2C level (`0xC0262582`). It isn't turned off anyway.
- **Any typed key, mouse click or wheel turn wakes**, after the 5 s grace.
- **A mouse move only wakes when it's deliberate**: the cursor has to span 100 px across or down within 1.5 s (`[input] mouse_move_px` and `mouse_move_window_s` in `sleepmode.toml`). An optical mouse left alone twitches a pixel or two now and then, which used to wake sleep mode in the night. It's a span, not a path length, so jitter wobbling back and forth never adds up, while a quick shake or a short push of the mouse covers it at once. A slow drift (under about 67 px a second) doesn't count either. The log says `not waking for N small mouse move(s)` (at most once a minute) and `real input: the mouse moving` when one does wake it.
- **Media keys the hooks see don't wake it**, so Bluetooth glasses and headsets don't either (taking the glasses off sends a pause). That covers play/pause, stop, next and previous, mute and volume, and the browser and launch keys, the keyboard's own media keys and volume roller included. A button that arrives as a HID consumer report or `WM_APPCOMMAND` never reaches the keeper's hooks; it counts as missed input (below), so it takes 3 separate presses within 5 s to wake it. The log names each key it ignored (`not waking for media key(s) 0xb3`) and what did wake it (`real input: key 0x41`).
- **If the keyboard and mouse hooks can't be installed**, the keeper logs it once and falls back to watching for any input, so media keys wake it again. That's better than never waking.
- **Input the hooks miss takes a few presses.** Windows keeps input meant for an elevated (admin) window or the lock screen from a non-admin hook, and silently drops a hook that runs too slow. The keeper then sees only `GetLastInputInfo` move.
  - Each miss reinstalls the hooks, so after Windows drops one, the first key (or its own release) only reinstalls it and the next key wakes.
  - Three counted misses within 5 s count as real input and wake it. Misses under 1 s after a counted one count as that one, so a press and its release count once. So keys typed into an admin window wake it after 3 separate presses within 5 s, or about 2.5 s of steady typing or mouse movement. A headset button the hooks do see is never a miss.
- **Topmost windows opened later**, such as an Allow/Deny dialog or a notification, show above the black windows.
- **The display timeout is held off** whenever there's a projector, whether the sky, a black page or a black window covers it, so the projector never loses its signal and switches itself off.
- **If the whiteboard daemon is down when a wake runs**, it stays in the night view (saved in `scene.json`) until something takes it out; the whiteboard doesn't yet check sleepmode's state when it starts.
- **`SC_MONITORPOWER` isn't used.** It powers off every display, the projector included. Many projectors then show "No signal" or switch themselves off, and only the remote can bring them back.
- **Monitors that vanish when powered off:** a monitor that drops off the display list when powered off over DDC/CI can't be woken over DDC. `wake` says so: press its power button.
- **The wake task needs you logged in.** It runs only while you're logged on (no admin, no stored password).
- **A sleep and a wake, or two sleeps, at the very same moment** (say the wake task firing just as you ask for sleep mode, or two agents asking at once) can interleave and leave a monitor off: a wake's "awake", or the older sleep's state, lands over the newer sleep, so its keeper exits. Touching the mouse won't help then: run `wake`. The MCP server runs its own calls one at a time; a lock across processes is a TODO in `control/machine.py`; since a failed sleep's rollback wakes inside sleep, the lock has to be re-entrant, or the rollback has to call a wake body that doesn't take it.
- **Lights OpenRGB can't reach stay on:** RAM that needs PawnIO (if it isn't installed), and a wireless headset (no host-side lighting control). Use `off_commands` for anything with its own tool.
- **Restore means a profile.** OpenRGB can't read some devices' colours back, so wake loads `day`; change the look in OpenRGB's window (the tray icon) and save it as `day` again. Without a `day` profile, the snapshot can't bring back lights OpenRGB never set.
- **OpenRGB's I2C/SMBus warning** (about PawnIO) pops up each time its window starts, including when sleep starts the server. Dismiss it; OpenRGB 1.0 doesn't keep "Don't show this message again".
- **A vendor's own lighting app** can fight OpenRGB over the lights; set its services to manual start.
- **If the keeper dies** (killed in Task Manager), the PC isn't held awake and input won't wake the screens. `status` warns about it, and `wake` still restores everything.

## Packages (`src/sleepmode/`)

| Package | Does |
|---|---|
| `config` | Paths, tunable values, the projector name match |
| `screens` | DDC/CI power (dxva2), black-window fallback, the projector split |
| `schedule` | Wake-time parsing, the one-shot scheduled task |
| `whiteboard_link` | The client side of the night view contract |
| `keeper` | The background process: keep-awake, black windows, wake on input |
| `control` | The sleep / wake / status state machine, its state file, the summaries |
| `lighting` | RGB lights off at sleep and back at wake: OpenRGB, Dynamic Lighting (stub), vendor commands |
| `shared` | `popen_detached`, used by `keeper` and `lighting` |
| `mcp_server` | The `sleep_mode_*` MCP tools |

`wiring.py` builds the real parts and `cli.py` is the command line. Each package has a README. Monitor listing comes from the shared `packages/displays` (`signal_displays`).

## Dependencies

- `mcp==2.3.0`, for the MCP server (the same pin as the other tools).
- `signal-displays` (`packages/displays`, stdlib only), for monitor listing and the projector pick, shared with the whiteboard's rules.
- `openrgb-python==0.3.8`, the client for OpenRGB's SDK server. It's a separate GPL-3.0 dependency installed from PyPI, not bundled with Signal; Signal itself is licensed under PolyForm Noncommercial 1.0.0 (see the root `LICENSE`).
- Everything else is the standard library (`ctypes`, `subprocess`, `threading`, `urllib`, `tomllib`).

## Tests

```
uv run pytest
```

They use fakes for the displays, DDC, the whiteboard (a fake daemon on a loopback port), Task Scheduler, OpenRGB's server, the keyboard and mouse hooks, and the keeper. No monitor or light is touched and no task is registered. The keeper tests start short-lived windowless processes of this venv's Python (two that sleep, which the backstop test ends, and one that exits at once). No real keeper runs.
