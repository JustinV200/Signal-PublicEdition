# whiteboard.config

Settings for every other whiteboard package: frozen dataclasses with defaults in code, an optional TOML override file, and the tool's well-known paths. Mirrors `audiohub.config` in style but imports nothing from it.

## Public API (`from whiteboard.config import ...`)

- `load_settings(path: Path | None = None) -> Settings`
  - With `None`, reads `DEFAULT_CONFIG_PATH` if it exists, otherwise returns defaults.
  - An explicit path must exist.
  - Raises `ConfigError` (a `ValueError`) on unreadable or invalid TOML, unknown sections or keys, wrong types, and out-of-range numbers. The message names the file and the `section.key`.
- `settings_from_dict(data, source)` validates an already-parsed mapping.
- `Settings` has one frozen section per TOML table: `display`, `camera`, `capture`, `watcher`, `agent`, `align`, `idle`. The section classes are exported too.
  - `agent` also holds `triage`, `triage_model`, `triage_timeout_s` and `verify_after_draw`.
  - `align` holds `auto`, `check_s`, `marker_check_s`, `drift_px` and `max_reprojection_px` for automatic re-alignment.
  - `idle` holds the idle view's `auto`, `empty_s`, `ink_quiet_minutes`, `locate`, `locate_hours`, `place`, `lat`, `lon`, `news_feed`, `news_source`, `weather_min`, `news_min` and `tag_labels` (`"tag=Label"` strings); see `daemon/idle/README.md`.
  - `camera.backend` must be one of `CAMERA_BACKENDS` (`msmf`, `dshow`, `any`).
  - An int is accepted where a float is expected. NaN and infinity are rejected.
  - Change a value with `dataclasses.replace`.
- Paths:
  - `TOOL_ROOT` is `tools/whiteboard`
  - `REPO_ROOT` is the monorepo root
  - `LIFE_DIR` is `<repo>/life`, the owner's KB (the TODO view reads its week plans)
  - `STATE_DIR` is `tools/whiteboard/.state` (gitignored): scene, calibration, snapshots, Edge profile, logs
  - `DEFAULT_CONFIG_PATH` is `tools/whiteboard/whiteboard.toml` (gitignored)

Every key, with its default, is documented in `tools/whiteboard/whiteboard.example.toml`.

## Files

- `paths.py`: path constants. They assume uv's editable install.
- `settings.py`: section dataclasses and defaults.
- `validation.py`: `ConfigError`, the `bounded()` and `one_of()` field helpers, and per-section type/range/choice checks.
- `loader.py`: reads TOML and builds `Settings`.

## Dependencies

Standard library only (`tomllib`, `dataclasses`, `typing`). Imports nothing else from whiteboard.
