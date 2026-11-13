# whiteboard.display.scene

The scene: what's projected, as frozen dataclasses changed only by pure functions.

## Public API (`from whiteboard.display.scene import ...`)

- Model: `Item {id, kind, x, y, w, h, content, style, created_by, created_at}`, `Style {color, stroke_width, font_size (0 = auto-fit), rough, opacity}`, `Scene {items, board_quad, view, night}`, `NightView {seed, sky, previous_view}` (set exactly while the view is night), `ITEM_KINDS`, `VIEWS` (`ITEMS_VIEW` "items", `TODO_VIEW` "todo", `IDLE_VIEW` "idle", `NIGHT_VIEW` "night") and `DAY_VIEWS` (the three the night view can hide).
- Errors: `SceneError` (a `ValueError`, for bad input), `ItemNotFoundError` (a `LookupError`), and `NightViewError` (raised by the board server when something would light up the board under the night view).
- Parsing (the trust boundary): `item_from_dict`, `style_from_dict`, `scene_from_dict`, `parse_view`, `parse_seed` (an integer 0 to 2^32 - 1, what the sky's generator takes), and back again with `item_to_dict` / `scene_to_dict`. A `scene.json` without `view` (older files) loads as `items`. Unknown keys, non-finite numbers and bad colours are rejected. A missing id becomes `<kind>-<8 hex>`.
- Content per kind (`content.py`):
  - `svg` is sanitized by `sanitize_svg`, which strips `<script>`, `<foreignObject>`, `<style>` (a stylesheet would restyle the whole page, hidden layers included), non-SVG elements, `on*`, non-`#` hrefs, `javascript:` and external `url()`. Colour SVG with presentation attributes (`fill`, `stroke`) or `style=""`. The page drops `<style>` too, so a saved board whose SVG used one loses those class styles.
  - `rough` is a JSON list of shapes in item-local pixels (`ROUGH_SHAPES`): `rect`/`ellipse {x,y,w,h}`, `line`/`arrow {x1,y1,x2,y2}`, `path {d}`, each with an optional `color` and `stroke_width`.
  - `image` is a repo-relative, forward-slash PNG/JPEG path inside `IMAGE_DIRS` (`tools/whiteboard/.state`).
    - `check_image_path` validates it as a string only. It rejects UNC, drive, rooted, `..`, `:` (ADS), `\`, device names and other extensions before any filesystem call, because resolving a UNC path leaks NTLM.
    - `resolve_image_path` (used by `/files` and on create/patch) then resolves links and junctions and requires an existing file inside the folder.
    - Loading `scene.json` never checks existence, so a pruned snapshot just renders nothing.
- Ops (`ops.py`): `upsert_item`, `patch_item` (style merges key by key; id and kind can't change), `remove_item`, `clear_items` (keeps the fit), `set_board_quad`, `find_item`.
- View ops: `switch_view` (items, TODO or idle), `show_drawn_items` (drawing anything but the thinking box switches to the items), `show_night(scene, seed, sky)` (remembers the view under it; shown again, only the sky changes) and `hide_night` (back to that view; a no-op outside it). Under the night view, `switch_view` and `show_drawn_items` only change the view it goes back to.
- Store: `SceneStore(path).load()` / `.save(scene)`. Saves are atomic. The idle view is written as `items` (as the view, or the night's `previous_view`), since older code rejects it; the daemon's rule brings it back. A corrupt file is moved to `scene.json.bad` and the scene starts empty.
- Board fit (`fit.py`): `parse_quad` (4 points TL, TR, BR, BL, clockwise and convex), `logical_size`, `stage_homography`, `css_matrix3d`, `stage_geometry`.
- Field validators shared with the server: `require_object`, `check_keys`, `require_number`, `require_positive`, `require_str`, `require_bool`.

## Dependencies

`numpy`, `whiteboard.config` (`REPO_ROOT`), `whiteboard.shared` (`write_atomically`). Standard library otherwise (`xml.etree` for SVG).
