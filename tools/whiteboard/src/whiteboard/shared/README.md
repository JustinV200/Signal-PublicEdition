# whiteboard.shared

Small helpers more than one whiteboard package needs. Add a helper here only once a second package uses it.

## Public API (`from whiteboard.shared import ...`)

- `write_atomically(path, data, unchanged_from=None)` (`files.py`): writes `data` to a temp file next to `path`, then swaps it in with `os.replace`, so a crash never leaves half a file. The folder must exist. With `unchanged_from`, the file is read again right before the swap and nothing is written if it no longer holds those bytes (`FileChangedError`, an `OSError`). The temp file is always cleaned up. Used by the scene store, calibration.json, the TODO store and the plan edit.
- `FractionBox` (`boxes.py`): an `(x, y, w, h)` box as fractions of the width and height. The board controller gives the idle ticker's band in it and the change watcher masks it out of the camera's live view.

## Depends on

The standard library only. Imports no other whiteboard package, so any package may use it.
