# analysis_chamber.gpu

Cross-process GPU lock so only one GPU step runs at a time (msvcrt byte lock on `state_dir/gpu.lock`).

## Public API

- `gpu_lock(state_dir, timeout_s=None)`: context manager. Blocks until held; raises `GpuLockTimeout` on expiry. Released on exit and by the OS if the process dies.
- `run_locked(state_dir, cmd) -> int`: runs `cmd` holding the lock, returns its exit code. The CLI's `analysis-chamber gpu -- <cmd>` wraps it.
- `GpuLockTimeout` (a `TimeoutError`).
- `KillOnCloseJob`: Windows job object (kill-on-close) used by `run_locked`; `add(process_handle)` and `close()`.

Depends on: the standard library only.

The lock is not re-entrant: never nest `analysis-chamber gpu` (or `gpu_lock`) inside a locked command, it would wait on itself forever. `run_locked` runs the command in a kill-on-close job object, so a hard-killed wrapper takes its child with it.
