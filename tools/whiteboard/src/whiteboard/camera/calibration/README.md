# whiteboard.camera.calibration

Maps camera pixels to the space Claude draws in. A projected ArUco pattern gives the camera-to-projector homography. An optional board fit then maps the projector stage onto the physical whiteboard.

## Public API (`from whiteboard.camera.calibration import ...`)

- `pattern_layout(projector_size=(1280, 720)) -> list[{id, x, y, size, png_bytes}]`
  - Six DICT_4X4_50 markers, 144 px tiles (108 px marker plus an 18 px white margin), inset 40 px from the stage edges.
  - The page draws each PNG at `(x, y)`, `size` px square, with `image-rendering: pixelated`.
- `await calibrate(camera, show_pattern, clear_pattern) -> Calibration`
  - `show_pattern` and `clear_pattern` are async callables from the daemon. `clear_pattern` always runs.
  - Hold the capture rig's `lock` around the call, so a clean capture can't restore the page mid-pattern.
  - It waits 1 s for exposure to settle, then tries up to 4 fresh frames.
  - Raises `CalibrationError` with a readable message when fewer than 3 markers are visible, or `CameraError` from the camera.
- `solve_calibration(frame, projector_size) -> Calibration`
  - The pure part. All 4 corners of every detected marker feed `findHomography` with RANSAC.
  - `reprojection_error_px` is the mean inlier error in projector px.
- `Calibration` holds `homography`, `camera_size`, `projector_size`, `reprojection_error_px`, `marker_count`, `created_at`, and the optional `board_quad` and `board_size`.
- `save_calibration(cal, path)` writes atomically. `load_calibration(path)` returns `None` if the file is missing and raises `CalibrationError` if it's invalid.
- **Board fit:**
  - `detect_board_quad(frame, cal) -> (4, 2) | None` finds the whiteboard's corners (TL, TR, BR, BL) in camera px. Use a blank-mode frame. Only bright quads whose centre is inside the projected area (the projector rect mapped into the camera with the inverse homography) and that don't touch the frame edge count, so a white wall around the board is skipped. The one overlapping the projected area best wins. `None` if none qualifies.
  - `board_quad_in_projector(quad_cam, H)` maps those corners to projector px.
  - `board_quad_in_camera(quad_proj, H)` maps them back, e.g. a fit to where the camera should see the board.
  - `board_view_size(quad_proj, height)` takes its width from the board's aspect ratio.
  - `fit_board(cal, quad_cam, height) -> Calibration` returns a copy with `board_quad` (projector px) and `board_size` set. The page warps its stage onto `board_quad`.
- **Rectifying:**
  - `rectify(frame, H, size=(1280, 720), scale=1)` is a plain warp.
  - `view_transform(cal) -> (M, size)` gives camera to board view when fitted, else camera to stage.
  - `rectify_to_view(frame, cal, scale=1) -> (image, is_rectified)` returns the raw frame when there's no calibration or the frame size doesn't match it.

Coordinates are CSS pixel edges: `(0, 0)` is the stage's top-left corner.

If the board is larger than the projection, parts of the board view are outside what the projector can reach.

Depends on `opencv-python` and `numpy`.
