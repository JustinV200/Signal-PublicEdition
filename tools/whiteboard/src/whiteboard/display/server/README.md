# whiteboard.display.server

The daemon's aiohttp app and the object that owns the live board.

## Public API (`from whiteboard.display.server import ...`)

- `BoardController(store, projector_size=(1280, 720), fit_height=720)`: the scene, display mode and connected pages. Every change is saved, then broadcast. It lives in the `board/` subpackage, split into the scene side (`SceneBoard`) and the mode, flash and TODO side on top (see [board/README.md](board/README.md)).
  - Async: `put_item`, `put_items(items, replace=False)` (one change for many items, e.g. a loaded board), `patch_item`, `remove_item`, `clear`, `set_fit(quad | None)`, `set_mode(mode, markers=())`, `highlight(Highlight)`, `set_view("items" | "todo")`, `set_todo(data, newly_done=())`, `show_night(seed)`, `hide_night()`.
  - Under the night view, `set_view` and drawing only change the view it goes back to, `set_mode` refuses every mode but `normal` and `highlight` refuses outright (`NightViewError`). `hide_night()` outside the night view saves and sends nothing.
  - Putting or patching any item but the "thinking" box switches the view back to `items`, so Claude never draws out of sight.
  - The TODO data isn't saved (the daemon rebuilds it from `life/`); the view is, with the scene.
  - Sync: `scene`, `mode`, `stage()`, `status()`, `todo_message(newly_done=())`.
  - `page_changed_s()`: monotonic time of the last push to the pages (scene, mode, TODO data; a highlight counts until it ends), or `math.inf` while a mode other than `normal` or the night view shows. While the idle view shows, the last minute boundary counts too, since its clock flips then (`board/minute.py`). The camera's change watcher settles after it, so the daemon's own flashes and drawings never trigger a clean capture.
  - `motion_masks()`: while the idle view shows, its news ticker's band as an `(x, y, w, h)` fraction of the board (`board/idle_ticker.py`: the NEWS footer plus 12 design px, placed the way the page scales its 1112x720 design onto the stage); else none. The change watcher leaves it out of its motion check, since the ticker scrolls all the time.
  - The camera package calls `set_mode("blank")` / `set_mode("pattern", markers)` in-process.
- `create_app(board, *, look=None, calibrate=None, status=None, page_token=None) -> web.Application`. The hooks are async callables (`LookHook`, `CalibrateHook`, `StatusHook`). A missing hook makes its endpoint answer 503. `page_token` turns on the page cookie guard (see Security); the daemon always passes it.
- `DISPLAY_MODES`, `Marker`, `Highlight`, `STATIC_DIR`, and `read_json_object(request)` (a request body as a JSON object, for the daemon's own routes).

## Routes

| Route | Body / result |
|---|---|
| `GET /board?token=` | checks the daemon token, sets the page cookie, redirects to `/board` |
| `GET /board` | the board page; `/static/...` serves its assets |
| `GET /files?path=` | a PNG/JPEG under `tools/whiteboard/.state/` (snapshots, `image` items); 404 otherwise |
| `GET /ws` | server → page: `{type: scene, items, board_quad, view, night, stage}`, `{type: mode, mode, markers}`, `{type: todo, todo, newly_done}`, `{type: highlight, x, y, w, h, seconds}`. A page that connects gets scene, mode and todo (with nothing newly done). Page → server: `{type: render_error, id, error}` (logged) |
| `GET /api/scene` | `{ok, items, board_quad, view, night, stage}` (`night` is `{seed, previous_view}` or null) |
| `POST /api/items` | an item → `{ok, id, item}` (creates, or replaces the same id) |
| `PATCH /api/items/{id}` | any of `x, y, w, h, content, style` → `{ok, id, item}` |
| `DELETE /api/items/{id}` | `{ok}`; 404 if unknown |
| `POST /api/clear` | `{ok}` (keeps the board fit) |
| `POST /api/highlight` | `{x, y, w, h, seconds=3}` (max 60 s) |
| `POST /api/mode` | `{mode, markers?}` |
| `POST /api/fit` | `{quad: [[x, y] x4] \| null}` → `{ok, stage}` |
| `POST /api/look` | `{clean=true}` → the look hook's result + `items`, `stage`, `view` |
| `POST /api/calibrate` | the calibrate hook's result |
| `POST /api/night/show` | `{seed?}` (sleep mode sends it; it defaults to tonight's `YYYYMMDD`, nights running noon to noon; an older sleepmode's `sky` is ignored) → `{ok, view: "night", seed, previous_view}` |
| `POST /api/night/hide` | body ignored → `{ok, view}`; outside the night view nothing changes |
| `GET /api/status` | `{ok, mode, view, item_count, pages_connected, stage}` + the status hook's fields |

Errors are `{ok: false, error}`: 400 for bad input, 404 for an unknown id, 409 for a flash or highlight under the night view, 503 when a hook is missing, and 500 (logged) for anything unexpected.

## Security

- `loopback_only` rejects a non-loopback `Host` (DNS rebinding) and a non-loopback `Origin` (cross-site POSTs and WebSockets).
- With `page_token`, everything outside `/api/` (the page, static files, `/files`, `/ws`) needs the `whiteboard_page` cookie. Only `/board?token=<daemon token>` sets it: HttpOnly, SameSite=Strict, holding an HMAC of the token rather than the token. `/api/*` is guarded by the daemon's token header.
- The board page has a Content-Security-Policy: only its own origin, plus `data:` images and inline styles (mermaid, KaTeX).
- Every response is `Cache-Control: no-cache`.

## Dependencies

`aiohttp`, `whiteboard.display.scene`.
