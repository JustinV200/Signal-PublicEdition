# sleepmode.keeper

The background process that holds sleep mode up all night: `python -m sleepmode keeper ...`, started by `sleep`.

## What it does

- **Keeps the PC awake** with `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)`, plus `ES_DISPLAY_REQUIRED` whenever there's a projector, so the display timeout can't switch it off. The power plan isn't touched, and Windows drops the request when the process ends.
- **Shows the black windows**: borderless, topmost, no taskbar button, no mouse pointer, one per display that couldn't be powered off.
- **Keeps the projector dark** (`night_guard.py`). It starts under a black window. Every `NIGHT_RETRY_S` (60 s), on a worker thread so the hooks never wait, it asks the whiteboard whether the night view is on a connected page: if so, the black window comes off; if not, it goes back on, and the next check asks for the night view again, then repairs the whiteboard if it's still not on a page (`NightView.repair`: start the daemon, or have it reopen its kiosk). So a whiteboard started after the sleep still gets the sky, and one that stops mid-night leaves black, not the desktop.
- **Wakes on real input.** A fresh press of any key (not a held key's auto-repeat, so a key stuck down can't wake it; each poll checks held keys with `GetAsyncKeyState`, so a release the hooks missed doesn't mute the key, and a stuck key's repeats don't count as missed input) but the media, volume, browser and launch keys (`VK_BROWSER_BACK` 0xA6 to `VK_LAUNCH_APP2` 0xB7), any mouse button or the wheel, or a deliberate mouse move, after a grace period (`INPUT_GRACE_S`, 5 s), closes the windows and runs the full wake (`input_watch.py`).
  - A move is deliberate once the cursor's positions within `mouse_move_window_s` (1.5 s) span `mouse_move_px` (100 px) across or down (`mouse_travel.py`; `sleepmode.toml`'s `[input]`, read once when the keeper starts). That ignores an optical mouse's jitter but not a shake of the mouse.
  - It sees input through low-level hooks (`WH_KEYBOARD_LL`, `WH_MOUSE_LL`; `input_hooks.py`) on its main thread. Its message loop (`message_loop.py`) serves both the hooks and the black windows, and waits for messages rather than sleeping, since Windows silently removes a low-level hook whose call waits too long.
  - Only the owner's own keyboard and mouse wake it. Input another program sent (`SendInput`, remote tools; the hooks' `LLKHF_INJECTED` 0x10 and `LLMHF_INJECTED` 0x01 flags) never does. It still counts as a hook call, since it moves the `GetLastInputInfo` tick too, so it can't wake it as missed input either. It's logged at most once a minute, like ignored mouse jitter.
  - Input the hooks never see (a HID-only media button, `WM_APPCOMMAND`) can't wake it with one press. A miss is a `GetLastInputInfo` move with still no hook call one poll later (the extra pump lets a late call land). Each miss reinstalls the hooks in case Windows removed one, so after a drop the first key (or its own release) only reinstalls them and the next key wakes. Misses under `MISS_MERGE_S` (1 s) after the last counted one count as it, so a press and its release count once. `MISSES_TO_WAKE` (3) counted misses within `MISS_WINDOW_S` (5 s) count as real input, since the hooks then can't see the owner at all (an elevated window has the focus, or the lock screen is up): 3 separate presses in 5 s, or about 2.5 s of steady typing or mouse movement.
- **Exits when sleep mode ends elsewhere.** Every second it reads the state file:
  - a wake (MCP, CLI, the wake task) marks the file awake, and a newer sleep gives it a new session id; either way the keeper just exits;
  - a missing or corrupt file makes it run the full wake, so the screens never stay dark with no record.
- **Fails safe.** If the keep-awake, the black windows or the input watch fail, it closes the windows, releases the keep-awake and runs the full wake (`KEEPER_ERROR`). If the hooks can't be installed, it logs that once and falls back to `GetLastInputInfo`, so any input wakes it, media keys and injected input included.
- **Logs to `.state/sleepmode.log`** through its own append-mode file handler, like every other `sleepmode` command. Its stdout and stderr go nowhere.

## Public API

- `run_keeper(options, read_state, wake, night=None) -> str`: the loop. `wake`, `read_state` and `night` (a `NightView(is_showing, show)`) are callbacks, so this package never imports `sleepmode.control` or `sleepmode.whiteboard_link`. Returns one of `decide`'s answers other than `KEEP`, or `KEEPER_ERROR`.
- `decide(reading, session_id, has_input) -> KEEP | EXIT | WAKE_ON_INPUT | WAKE_LOST_STATE`: the pure decision, tested.
- `KeeperOptions(session_id, rects, keep_display_on, grace_s, projector=None)`, `keeper_command(options)`. `rects` never holds the projector: `projector` is the rect the night guard keeps dark.
- `start_keeper(options, startup_check_s) -> KeeperProcess(pid, created)`. It raises `OSError` if the keeper can't start or exits within `startup_check_s` (`KEEPER_STARTUP_CHECK_S`, 2 s). If the check fails or is interrupted (Ctrl+C) while the process is up, it ends that process first, since the caller never learns its pid.
  - The keeper starts in `tools/sleepmode` with `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`, and `CREATE_BREAKAWAY_FROM_JOB` when allowed (`sleepmode.shared.popen_detached`), so it outlives its starter.
- `is_process_alive(pid, created=None)` and `process_creation_time(pid)`, re-exported from `sleepmode.shared`. Also `StateReading`.
- `stop_keeper(pid, created, wait_s)`: the backstop for wake, and for a sleep that replaces another. It gives the keeper `wait_s` to exit by itself, then ends it with `TerminateProcess`, but only if that pid's creation time still equals `created`. So a reused pid is left alone (and not waited on), even another python from this venv, and with `created=None` (an older state file) nothing is ended. It never touches the calling process or its parent.
  - The recorded pid is the venv's `python.exe`, a launcher that runs the real interpreter as its child and ends it along with itself. So ending the pid ends the keeper, inside the keeper that pid is the parent, and the recorded creation time is the launcher's.

## Depends on

`sleepmode.config` (`TOOL_ROOT`), `sleepmode.shared` (`popen_detached`, `is_process_alive`) and the standard library (`ctypes`, `subprocess`, `threading`).
