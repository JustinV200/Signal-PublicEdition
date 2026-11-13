# browser_tool.downloads

Saves the desktop browser's downloads into one folder (`[downloads] folder`, default `tools/browser/.downloads/`, gitignored), within a size cap. Docker jobs never get here: their backend denies downloads over CDP.

## Public API (`from browser_tool.downloads import ...`)

- `DownloadRecorder(settings, policy)`, owned by `BrowserSession` as `session.downloads`:
  - `watch(context, incoming)` saves every download from every open and future tab. The session calls it only when the backend has an incoming folder (`LocalBackend` with `[downloads] enabled`).
  - Each download's source must pass the host policy: its URL (the final one, after redirects), or for a `blob:` or `data:` download the page that made it. Otherwise it is cancelled.
  - While it runs, a file in the incoming folder past `[downloads] max_mb` cancels it (the partial is deleted). A finished file over the cap is deleted too. No growth in the incoming folder for `STALL_S` (60 s), or a run past `MAX_DOWNLOAD_S` (30 minutes), cancels it as well. Playwright's own copy is deleted whether or not the save worked.
  - A finished download is copied to `safe_file_name(suggested name)` through `reserve_path`, and Playwright's copy is deleted. Nothing is ever opened, run or unpacked.
  - `collect(started_before, timeout_s)` waits up to `timeout_s` only for downloads started after `started_before` (older running ones aren't waited for) and returns the finished ones once (`SavedDownload`: the untrusted original name, the path or the problem, the size), plus how many still run. It never raises.
  - `started` counts downloads; `wait_for_start(started_before, timeout_s)` lets `navigate` tell a URL that started a download from a failed load (Playwright fails `goto` with "Download is starting" just before the event).
- `safe_file_name(suggested)`: replaces path separators, Windows' forbidden characters and Unicode control and format characters (`Cc`, `Cf`: C0, C1, bidi overrides, zero-width, BOM) with `_`, adds `.download` to `.url`, `.scf`, `.lnk`, `.library-ms` and `.searchconnector-ms` names, strips leading and trailing dots and spaces (so no `.` or `..`), prefixes Windows device names (`CON`, `nul.txt`, `COM1`...) with `_`, caps the length at 120 keeping the extension, and falls back to `download`.
- `reserve_path(folder, name)`: creates the file exclusively, adding ` (1)`, ` (2)`... on a clash, so nothing is overwritten. Refuses a name that would land outside the folder.
- `INCOMING_FOLDER_NAME` and `clear_folder(folder)`: the backend's in-flight folder inside the profile, cleared of leftovers before each launch (left alone if it is a symlink or junction).

## Files

- `file_names.py`: the sanitizing and the clash-free reservation.
- `incoming.py`: the in-flight folder (biggest file, leftover cleanup).
- `recorder.py`: `DownloadRecorder` and `SavedDownload`.

## Dependencies

`playwright`, `browser_tool.config` and `browser_tool.policy`.
