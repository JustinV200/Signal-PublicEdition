# analysis_chamber.runs

A run's folder and its `manifest.json`: the record every other package reads and checkpoints.

## Public API

- `Phase` (plan, collect, analyse, critique, report), `PHASE_ORDER`, `Status` (awaiting_approval, queued, running, done, failed, cancelled). Both are `StrEnum`s.
- `Manifest` dataclass, `to_dict()` / `Manifest.from_dict(data)`, `SCHEMA_VERSION = 1`, `REPORT_FORMATS`. `from_dict` raises `ManifestError` on another schema version or a bad field.
- `read_manifest(run_dir) -> Manifest`, `write_manifest(run_dir, manifest) -> Manifest` (atomic, returns the copy with `updated_at` bumped).
- `make_opaque_id(today, taken) -> str`: `<YYYY-MM-DD>-p-<4 hex>`; every new run starts with one.
- `make_run_id(question, today, taken) -> str`: `<YYYY-MM-DD>-<slug>`, `-2`, `-3` on a clash; the daemon renames a run to it when approved as non-personal.
- `create_run_dir(root, run_id) -> Path`: the subfolders in `RUN_SUBDIRS` and a per-run `.gitignore`.
- `scan_runs(roots) -> list[(Path, Manifest)]`: skips unreadable manifests, and manifests whose id isn't the folder name, with a logged warning.
- `move_run(run_dir, dest_root) -> Path`.
- `utc_now_iso()`, `MANIFEST_NAME`.

New runs are created under `private_root`. On approval with `personal=False` the daemon moves them to `analyses_root` (see `DESIGN.md`).

## Depends on

`signal_jsonstate` (atomic writes) and the standard library.
