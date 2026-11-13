# browser_tool.actions.page

The tools that read the current tab. Public API (re-exported by `browser_tool.actions`): `snapshot`, `find`, `wait_for`, `screenshot`.

- `snapshot.py`: `snapshot(ctx, ref=None, page=1)` serves one page, or one ref's subtree, of the tab's redacted and scrubbed snapshot. `take_snapshot` and `cached_or_fresh` are shared with find and wait_for.
- `find.py`: `find(ctx, text, max_results=20)` searches the cached snapshot.
- `wait_for.py`: `wait_for(ctx, ...)` waits, read only, for text, a ref to go, a URL or network idle. Text and URL are matched only on scrubbed text.
- `screenshot.py`: `screenshot(ctx, ref=None, full_page=False)` saves a masked PNG of the viewport, the whole page or one element.
- `paging.py`: pure helpers for pages, subtrees and search over snapshot text.

All four tools refuse while the vault reports filled fields; `find` and `wait_for` refuse a Duo tab first. Depends on `actions` (context, guards, secret_scrub, snapshot_cache, untrusted, signin), `policy` and `redaction`. Details are in `../README.md`.
