# analysis_chamber.guard

The daemon's leak guard: personal runs never land in the repo or in a published artifact.

## Public API

- `check_run_location(manifest, run_dir, config) -> None`: raises `LeakError` if a run with `personal` True or None is under `repo_root` or not under `private_root`, or a run with `personal` False isn't under `analyses_root`. The daemon calls it before creating, moving or writing into a run folder.
- `can_publish(manifest) -> bool`: True only when `personal is False` and `report_format == "artifact"`.
- `is_under(path, root) -> bool`: resolved containment check, case-insensitive on Windows (WindowsPath compares that way). Reuse it for any path check (the agents' write hook too).
- `LeakError`.

## Depends on

`analysis_chamber.config`, `analysis_chamber.runs`.
