# whiteboard.camera

The webcam side of the whiteboard. It captures frames, calibrates camera pixels to the projector stage and the board, takes clean captures with the projection briefly off, watches the board for new ink, and notices when the alignment has drifted.

## Public API (`from whiteboard.camera import ...`)

### Capture
- `Camera(camera_settings)`
  - A context manager, or call `open()`/`close()`.
  - A daemon thread keeps the newest frame. `latest()` never blocks and returns `None` when there's no frame from the last 2 s. The watcher samples it, and so does the daemon's live stream (`/api/camera/stream`), so watching live never opens the device a second time. `read_fresh(timeout_s=3)` waits for a frame exposed after the call, and `close()` wakes it.
  - If reads keep failing (unplugged), the thread reopens the device, retrying 1, 2, 4 ... 30 s apart.
  - `info` reports the open backend, width, height and fps.
  - Backend choice: the configured backend first, then MSMF, then DirectShow. It keeps the first one that delivers the requested size; if none does, it uses the first that opened, with a warning. It asks for MJPG so 1080p streams at full rate.
  - Raises `CameraError`.
  - On the USB Webcam, MSMF opens in about 1.3 s and streams 1920x1080 at 30 fps. DirectShow opens it but delivers about 2 fps of black frames.
- `list_cameras(width=1920, height=1080) -> list[CameraInfo]` probes indexes 0-4 on MSMF and DirectShow. It opens each device, so don't run it while the daemon holds the camera.

### Clean capture
- `CaptureRig(camera, set_mode, snapshot_dir, blank_ms, keep_snapshots, calibration=None, page_changed_s=..., motion_masks=...)`
  - The daemon owns one and replaces `calibration` after calibrating or fitting.
  - `rig.lock` (an `asyncio.Lock`) is held by every capture from blank to restore. Hold it around `calibrate()` too. Copies made with `dataclasses.replace` share it.
  - `set_mode` is an async callable that pushes `"blank"` or `"normal"` to the page.
  - `page_changed_s()` says when the daemon last changed the page itself (monotonic s), or `math.inf` while a blank, the markers, the fit outline or the night view shows. The daemon passes `BoardController.page_changed_s`; the default (`-inf`) means never.
  - `motion_masks()` gives the parts of the page that move by themselves, as `(x, y, w, h)` fractions of the board view (the idle view's news ticker; the daemon passes `BoardController.motion_masks`). The default is none.
- `await clean_capture(rig) -> (png_path, is_rectified)`
  - Blank, wait `blank_ms`, take a fresh frame, then restore `normal`. The restore always runs.
  - It then rectifies to the board view and saves a PNG, keeping the newest `keep_snapshots`.
  - Without a usable calibration, the PNG is the raw frame and `is_rectified` is `False`.
  - If the camera is stale, it raises `CameraError` without blanking the page.
- `await grab_clean_frame(rig) -> CleanFrame(image, is_rectified, calibration, raw)` is the same without saving. `calibration` is the one it used and `raw` is the unrectified camera frame.
- `keep_mode` is a `set_mode` that leaves the page alone: `replace(rig, set_mode=keep_mode)` takes a capture with the projection on.

### Change watcher
- `ChangeWatcher(rig, watcher_settings, on_board_changed, on_clean_frame=None)`
  - Run `await watcher.run()` as a task and cancel it to stop.
  - `on_clean_frame(clean, now_s)` gets every clean capture (the drift monitor checks it). `last_motion_s` is the monotonic time of the last motion.
  - Each `sample_s`, it compares the live view with the last sample, matched to its brightness. A changed-pixel fraction over `motion_ratio` (at `pixel_threshold` grey levels) marks a capture pending. Each rectified live sample has `rig.motion_masks()` blacked out first (`without_regions`; a raw, uncalibrated frame doesn't line up with them, so it gets none), so the scrolling news ticker never counts as motion or as a large change, and the drift monitor (which reads `last_motion_s`) still sees the board as idle. Clean captures blank the whole page, so ink drawn in a masked band still counts once something else makes a capture due.
  - Every clean capture blanks the board, so it only takes one when it's worth it:
    - **settle:** for `settle_s` after `rig.page_changed_s()` (any blank or marker flash, a drawing, the TODO view) or its own capture, it samples nothing, and the first sample after is the new reference. Under the night view that time is `math.inf`, so it samples nothing all night. The daemon's own flashes and the camera's exposure swing after them never schedule a capture.
    - **stable:** `stable_s` without motion.
    - **dark:** none while the live camera frame's median grey is under `dark_floor` (`darkness.DarkRoom`, logged once per dark spell). The projected page is mostly black, so that median is about the room light. `is_room_dark()` asks the same DarkRoom, for the drift monitor.
    - **throttle:** at least `min_interval_s` since the last capture, unless the live view already shows 10x `ink_change_ratio` of new ink (`LARGE_CHANGE_FACTOR`, `added_ink_ratio`) against a reference taken after the last settle, so the daemon's own drawings never count.
  - It diffs ink masks (blur, then adaptive threshold) against the last reported capture, allowing 2 px of shift. A mask pixel must also be darker than the board around it (`darker_than_board`), so the halo round the projector's glare spot, which a plain adaptive threshold takes for ink, almost never counts. A dark pixel also stops counting where a whole `BOARD_FILL_PX` (61 px) square of dark area fits over it, so a mark narrower than 61 px in at least one direction (a stroke, a 120x40 filled box) counts, but the middle of a body doesn't (its uneven edge and an arm still can). The darker frame is first scaled up to the brighter one's median, so a faint stroke keeps its contrast. Changed blobs count only if big enough and if their peak change in fine detail (grey minus a 61 px box blur, so the room light's slow gradients drop out) beats 5x the frame's noise (`NOISE_K`); the outer `BORDER_NOISE_PX` strip, which flickers where the fit meets the board's frame, doesn't count.
  - When the changed fraction is at least `ink_change_ratio`, it saves a snapshot and awaits `on_board_changed(png_path, (x, y, w, h))`. The bbox is in that image's px.
  - The first capture is the baseline and isn't reported.
  - A failed capture waits for new motion instead of retrying, unless there's no baseline yet.
- The pure detection math lives in `detection.py`: `match_brightness`, `motion_frame`, `motion_ratio`, `ink_mask`, `ink_change`, `added_and_erased_ink` (the ink added and the ink erased, noise-gated the same way, for the TODO view's cross-out check) and `added_ink_ratio` (added ink outside the border strip, for the large-change check). `BORDER_NOISE_PX` is exported for the cross-out check's own border rule. `ink_change` and `added_ink_ratio` are exported for the idle view's wiped-ink and new-ink checks (`daemon/idle/ink_watch.py`). `darker_than_board(gray, contrast)` (pixels more than `contrast` below a 61 px grey closing, `BOARD_FILL_PX`: the board with every dark mark a 61 px square can't fit inside filled in; the middle of a dark area that square fits in doesn't count, though its uneven edge can) is exported for the saves' ink extraction too.

### Drift monitor (`drift.py`)
- `DriftMonitor(rig, align_settings, realign, BoardActivity(last_motion_s, is_busy, is_dark))`
  - Run `await monitor.run()` as a task. Hand `monitor.on_clean_frame` to the watcher.
  - A check finds the board outline (`detect_board_quad`) in a raw blank-page frame and compares it with the fit mapped back into camera px (`board_quad_in_camera`). The result is the mean corner error in camera px.
  - Checks come from every watcher capture, plus a capture of its own every `check_s` while idle (no motion and no page change for 30 s by `rig.page_changed_s()`, and `is_busy()` false). That's never during a flash, a fit show or the night view (`math.inf`), and not in the 30 s after one, so checks that came due overnight don't flash the moment the night view ends.
  - Two checks in a row over `drift_px` call `await realign(reading)`, again only when idle. A check that finds no outline counts for nothing. A good check, or a new calibration or fit, resets the count, and so does a re-align, so a failing one isn't retried every tick.
  - A photo check only sees the board move in the camera frame (camera or board moved). So every `marker_check_s` while idle it also calls `await realign(None)`, a marker check that catches a projector move.
  - Neither timed check runs while `is_dark()` (the watcher's `is_room_dark`) says the room is too dark; a skipped one stays due and runs once the light is back. A re-align after confirmed drift isn't timed, so it still runs.
  - `is_drifted` says whether the latest check that found the board's outline was over `drift_px`. One that found no outline (someone in front of a corner) doesn't clear it; a new calibration or fit does. While the watcher reports a change, that's usually the check of the change's own capture: the TODO view's cross-out check ticks nothing then.
- `await check_drift_now(rig) -> DriftReading(error_px, detected, expected, calibration, note)` takes one clean capture and measures it. `error_px` is `None` when there's no fit, no outline, or a frame-size mismatch, and `note` says which.
- `corner_error(quad_a, quad_b)` is the mean corner distance.

### Telling what moved (`movement.py`)
- `homography_drift_px(old_H, new_H, projector_size)`: how far the projector's corners moved in the camera between two solves (mean, camera px).
- `camera_shift_px(reference, frame) -> float | None`: how far the room moved between two blank frames. It takes the largest phase-correlation shift of the four quarters, so a roll or zoom counts too. New ink barely registers. `None` if the sizes differ.
- `ReferencePhoto(png_path)`: `load(marker)` / `save(frame, marker)` for the blank photo of the last confirmed alignment, tagged with the marker calibration's `created_at`.

### Calibration
`pattern_layout`, `calibrate`, `solve_calibration`, `Calibration`, `save_calibration`/`load_calibration`, the board fit (`detect_board_quad`, `board_quad_in_projector`, `board_view_size`, `fit_board`) and `rectify`/`view_transform`/`rectify_to_view` are re-exported from `calibration/`. See [calibration/README.md](calibration/README.md).

## Depends on
`whiteboard.config` (`CameraSettings`, `WatcherSettings`, `AlignSettings`), `whiteboard.shared` (`write_atomically`), `opencv-python` and `numpy`.
