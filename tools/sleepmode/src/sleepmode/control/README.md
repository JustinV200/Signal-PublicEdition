# sleepmode.control

The sleep / wake / status state machine, its state file, and the text summaries.

## Public API

- `SleepMode(deps)`:
  - `sleep(wake_at=None, night_sky=True) -> SleepState` turns sleep mode on, or updates it if it's on.
    - First saves the new session id, so an older keeper's input wake sees a newer sleep and does nothing.
    - Sets the wake task first, so a hung `schtasks` leaves the screens lit. With no `wake_at` while already asleep, the pending wake time is kept; otherwise any old wake task is removed.
    - Turns the RGB lights off (`deps.lighting.off`). That's before any screen goes dark too, so a lighting step that hangs leaves the screens lit, not dark with no keeper. It's also before the keeper starts, so no input wake can restore the lights while they're still going off. When it replaces a sleep that's still on, it passes `may_snapshot=False`, so that sleep's snapshot of the lights isn't saved over. A lighting failure is a note, never an error, and if a later step fails, the rollback's wake brings the lights back.
    - Darkens every display but the projector, then asks the whiteboard for the night view. If the whiteboard can't, the projector gets a black window, and `deps.start_whiteboard` starts the whiteboard daemon if it's down (a failed start is a note). This projector step is in `projector_step.py`.
    - Saves the state, then starts the keeper, which must still be running a moment later, then saves its pid. A keeper of the sleep it replaced that hangs on is then ended.
    - Raises `ValueError` for a bad or past `wake_at` (before anything changes). Raises `SleepModeError` if the displays can't be listed or the state can't be saved (nothing changed). Any failure after the session id is saved, the keeper not starting or dying at once included, wakes everything back up (the lights too), ends this sleep's keeper (if it started) and a replaced keeper that hang on, and then raises `SleepModeError` (Ctrl+C gets the same clean-up and is re-raised). If that wake itself fails, this sleep's keeper is left up, since the screens may still be dark and it's what wakes them on input.
  - `wake(reason="request", only_session=None) -> SleepState` turns sleep mode off (in `wake.py`). It sends DDC power-on to every display but the projector the sleep recorded, tells the whiteboard to leave the night view, and marks the state awake, so the keeper exits. Then it brings the lights back (`deps.lighting.restore`, skipped when the state says no sleep is on, so a repeat wake leaves them be) and removes the wake task, both after the save so slow lights or a hung `schtasks` can't hold the black windows up. Their notes are in the answer and the log, not the saved state. Last, `stop_keeper` ends a keeper that's still running a few seconds later. That last step runs even if the awake state couldn't be saved or Ctrl+C lands during `schtasks`.
    - Every step runs even without a readable state file. Failures become `notes`, never errors, so it's idempotent and always restores what it can.
    - `only_session` makes it a no-op when the state file names another sleep or says awake: the keeper passes its own, so a replaced keeper can't wake a newer sleep. A state file that can't be read doesn't stop it.
  - `status() -> SleepStatus(state, is_keeper_running)`. The keeper counts as running only if its pid is alive with the recorded start time.
- `SleepDeps`: the collaborators, built in `sleepmode.wiring`. Tests pass fakes for the `Screens`, `NightView`, `Scheduler` and `Lights` protocols and the callables.
- `SleepState`, `save_state(path, state)` (atomic, retries while the keeper has the file open) and `load_state(path) -> SleepState | None`. Sleep and wake read it with `load_state_quietly`, which logs and returns None for an unreadable file.
  - `load_state` raises `StateFileError` for a malformed file, and `OSError` for a transient read failure.
- `describe_sleep`, `describe_wake`, `describe_status`: the plain-text answers for the CLI and the MCP tools.

## The state file (`tools/sleepmode/.state/state.json`)

It holds `is_asleep`, `session_id`, `since`, `wake_at`, `night_sky`, `monitors` (one `MonitorResult` per display), `keeper_pid`, `keeper_created` (the keeper's creation time as a FILETIME count), `woke_at`, `woke_by`, `lighting` (what the last sleep did to the lights, one line per backend) and `notes`. The times are local ISO.

## Depends on

`sleepmode.screens`, `sleepmode.schedule`, `sleepmode.whiteboard_link`, `sleepmode.keeper` (`KeeperOptions` and `KeeperProcess` only), `sleepmode.lighting` (`LightingReport` only) and `signal_displays`.
