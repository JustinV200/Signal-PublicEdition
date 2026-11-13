# whiteboard.display

Everything the projector shows: the scene model and its store, the daemon's HTTP/WebSocket server, the projector finder and Edge kiosk, and the board page itself. Other whiteboard packages import from `whiteboard.display` only.

## Subpackages

- `scene/`: the scene model, pure ops, JSON parsing and validation, SVG sanitizing, the `scene.json` store, and the board-fit math. See its README.
- `server/`: `BoardController` (the live scene, mode and pages) and `create_app` (the aiohttp app). See its README.
- `screen/`: `find_projector` (ctypes monitor enumeration) and `launch_kiosk` (Edge fullscreen on the projector). See its README.
- `static/`: the board page (`board.html`, `board.css`, `todo.css`, and ES modules `board.js`, `stage.js`, `renderers.js`, `diagrams.js`, `todo.js`, `dom.js`), the idle view in `idle/` and the night sky in `night/` (see their READMEs), plus vendored JS in `vendor/` (versions in `vendor/README.md`).

## Coordinates

- **Projector pixels:** the projector's logical size, i.e. physical pixels / Windows display scale. A 1920x1080 projector at 150% is 1280x720. Pattern markers and the board quad use this space.
- **Stage pixels:** what item and highlight boxes use. With no board fit, the stage is the projector. With a fit (`POST /api/fit`), the stage is the board: its height is `display.fit_height` and its width follows the board's aspect ratio. The page warps it onto the quad with a CSS `matrix3d`, and nothing outside the quad is lit. `GET /api/status` reports `stage.width`/`stage.height`.
- `stage_homography(quad, size)` maps stage to projector pixels. Invert it to warp camera images into board space.

## Display modes

`normal` (the scene), `blank` (all black, for clean camera captures), `pattern` (only calibration markers `{url, x, y, w, h}` in projector pixels; url is `data:image/...` or a same-origin path), `fit` (the scene plus a green outline of the board quad, or of the whole projector).

## Views

Separate from the modes, the scene's `view` says what the page shows: `items` (the projected items), `todo` (the TODO view, `static/todo.js`, drawn from data the daemon pushes; see `whiteboard.todo`), `idle` (the default when nothing is drawn, `static/idle/`, from data the daemon pushes; see `whiteboard.idle`; the board agent's "thinking" box still shows over it) or `night` (sleep mode's dim sky, `static/night/`, on the board like the others). The other layers are hidden, not cleared, so switching back is instant and nothing is lost. The view is saved in `scene.json`. Drawing, moving or loading items switches back to `items`; the "thinking" box doesn't. `todo.js` builds every element with `textContent`, so plan text can't inject markup, and only animates a row it had itself shown open.

The night view sits on top of the other three. The scene keeps its `{seed, sky, previous_view}`; switching views or drawing under it only changes `previous_view`, and hiding it goes back there. While it shows, `BoardController` refuses every mode but `normal` and every highlight (`NightViewError`, HTTP 409), and `page_changed_s()` is `math.inf`, which keeps the camera's watcher and drift monitor paused. On the page, `board.js` starts the sky (`night/night.js`) when a scene message brings new night settings and stops it when the view changes, and `board.css` hides the other layers, the markers and the fit outline under it.

## Dependencies

`aiohttp`, `numpy` (homography solve), `whiteboard.config`. Windows-only APIs via ctypes (`user32`, `shcore`). PowerShell is used to find the kiosk's Edge process.
