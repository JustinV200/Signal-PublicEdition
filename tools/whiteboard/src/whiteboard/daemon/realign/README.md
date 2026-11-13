# whiteboard.daemon.realign

Re-aligns the board when the camera, the projector or the board has moved: it re-solves the marker calibration and moves the fit with it, or keeps the old alignment and says why.

## Public API (`from whiteboard.daemon.realign import ...`)

- `Realigner(context, align_settings)`: one per daemon, shared by the drift monitor and `POST /api/align/realign`. The reference photo is `context.reference`.
- `await realigner.realign(drift=None) -> RealignResult`
  - `drift` is the drift monitor's last drifted reading, or `None` for a marker check (periodic, or on request).
  - Under `rig.lock` it flashes the markers and solves. It rejects the solve if the reprojection error is over `max_reprojection_px`. Then it takes a blank photo and places the board in the camera:
    1. the detected outline, if it's within `drift_px` of the drift check's outline (or, with no reading, of where the old fit puts it)
    2. otherwise the old outline carried over (old H⁻¹, then the new H), but only if the camera hasn't moved: the largest per-quarter phase-correlation shift against the reference photo must be at most `drift_px / 2`
    3. otherwise it rejects
  - It applies the new calibration when the projector corners moved more than `drift_px`. It moves the fit when the old fit lands more than `drift_px` off the board and the estimate's own error is smaller (never worse). Otherwise the result is "nothing moved". That photo becomes the reference only if there is none yet for this calibration: never refreshing it keeps a camera that creeps a little per check from dragging it along.
  - A change shows "Re-aligned to board" for 3 s. Items are rescaled when the logical board width changes.
- `RealignResult(ok, changed, message, numbers)`. `to_dict()` gives `{ok, changed, message, projector_drift_px, camera_shift_px, reprojection_error_px, before_px, after_px}`, in camera px except the reprojection error. A key is left out when it wasn't measured.

## Files

- `realigner.py`: the decision.
- `apply.py`: saving and applying a new alignment, rescaling items, the toast.

The reference photo lives in `.state/align-reference.png`, tagged in `align-reference.json` with the marker calibration it belongs to. A manual `whiteboard calibrate` saves a fresh one from its own blank photo.

## Depends on

`whiteboard.camera`, `whiteboard.config`, `whiteboard.daemon.camera_hooks`, `whiteboard.display`, `whiteboard.saves` (`scale_items`).
