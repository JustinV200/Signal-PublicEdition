# whiteboard.saves

Save a whole whiteboard and bring it back later. A save is a folder `.state/boards/<slug>/`:

| File | What it holds |
|------|---------------|
| `meta.json` | `name`, `slug`, `description`, `created_at` (UTC ISO), `item_count`, `board_size` [w, h] in board pixels (checked finite, 1 to 100000 on read), `has_ink`, and `refresher` (`tasks` or `todo`) when the save has one; any other refresher is refused on save and on read. |
| `scene.json` | A copy of the projected items (scene.json format, validated again on load). |
| `images/` | Copies of the files image items point at, so they survive pruning, deletes and re-saving a loaded board over itself (`bundle.py`). |
| `photo.png` | The clean, rectified board photo (calibrated saves only). |
| `ink.png` | The owner's strokes as RGBA on a transparent background (calibrated saves only). |

Ink extraction (`ink.py`): an adaptive threshold (31 px block, 15 levels darker than the neighbourhood) finds the dark strokes, keeping only pixels also 15 levels darker than the board around them (`whiteboard.camera.darker_than_board`, a 61 px grey closing), so the halo round the projector's glare spot almost never comes out as ink. Of a filled mark only the outline is kept; that outline survives for a mark narrower than 61 px in at least one direction (a 120x40 box is kept), and is dropped only where a whole 61 px square of dark area fits over it. In pitch dark (median grey under about 20), a stroke within about 25 px of the glare spot loses most of its pixels. Each stroke pixel gets a bright, fully saturated version of its own hue, and black or grey ink (chroma under 40) becomes white, so it shows on the projector's black. Then a 3x3 dilation. The values were tuned on the real board, where they drop erased-marker ghosting and the board's edges.

Loading (`restore.py`) scales item boxes by `current size / saved board_size` (content and font sizes stay as saved), rebuilding each through the scene parser so an overflowing box is a `SaveError`. It adds `ink.png` as an image item `saved-ink-<slug>` covering the board, underneath the other items; a saved item that already has that id (the old ink of a board re-saved after loading) gets a fresh id. Image items whose file is gone (a pruned snapshot, a deleted save) are left out, not fatal.

## Public API

- `slugify(name)`: lowercase `[a-z0-9-]`, accents folded, at most 48 chars, Windows device names get `-board`. Raises `SaveError` when nothing is left.
- `parse_save_request(body)` → `SaveRequest(name, slug, description, overwrite)`. `parse_load_request(body)` → `LoadRequest(slug, replace, include_ink)`. `parse_name(body)`. `LOAD_MODES`.
- `SaveStore(root, repo_root=REPO_ROOT)`: `require_free(slug, overwrite)`, `save(request, items, board_size, images)` (temp folder, then renamed into place), `load(slug)` → `SavedBoard(meta, items, board_size, ink_content)`, `list_saves()` (newest first; unreadable folders are logged and skipped), `delete(slug)`.
- `restored_items(saved, current_size, include_ink)`, `scale_items(...)`, `drop_missing_images(items)`.
- `extract_ink(photo_bgr)` → BGRA array, `encode_png(image)`. `PHOTO_FILE`, `INK_FILE`.
- `SaveError` (a `SceneError`, so HTTP 400) and `SaveNotFoundError` (an `ItemNotFoundError`, HTTP 404).

The daemon's `/api/saves` routes (`daemon/save_routes.py`) do the capture and talk to the board.

## Depends on

`whiteboard.config`, `whiteboard.display.scene`, `whiteboard.camera` (`darker_than_board`), `opencv-python`, `numpy`.
