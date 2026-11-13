# sleepmode.config

Paths, tunable values, and the optional per-machine `sleepmode.toml`.

## Public API

- Paths: `TOOL_ROOT`, `REPO_ROOT`, `STATE_DIR` (`.state/`, gitignored), `STATE_FILE`, `LOG_FILE`, `CONFIG_FILE` (`sleepmode.toml`, gitignored), plus the whiteboard's `WHITEBOARD_ROOT`, `WHITEBOARD_STATE_DIR` and `WHITEBOARD_CONFIG`.
- Values (`settings.py`): `DDC_OFF_VALUE` (4, DPM off), `DDC_SETTLE_S`, `INPUT_GRACE_S`, `KEEPER_EXIT_WAIT_S`, `WAKE_TASK_NAME`, `WAKE_TASK_TIME_LIMIT`, `DEFAULT_PROJECTOR_MATCH`.
  - Lighting: `LIGHTING_STEP_TIMEOUT_S` (each backend's deadline, built from OpenRGB's start and CLI waits so both fit), `LIGHTING_COMMAND_TIMEOUT_S`, `OPENRGB_HOST`/`OPENRGB_PORT`, `OPENRGB_DEFAULT_PARTS`, `OPENRGB_START_TIMEOUT_S`, `OPENRGB_SETTLE_S`, `OPENRGB_CLI_TIMEOUT_S`, and the profile names `DAY_PROFILE` (`day`) and `SNAPSHOT_PROFILE` (`sleepmode-before`).
- `load_lighting_settings(path=CONFIG_FILE) -> LightingSettings(enabled, openrgb_path, off_commands, restore_commands)` reads `[lighting]` (`config_file.py`; `sleepmode.example.toml` documents the keys). A missing file means the defaults. An unreadable file, an unknown section or key, or a wrong type raises `ConfigError`.
- `load_input_settings(path=CONFIG_FILE) -> InputSettings(mouse_move_px=100, mouse_move_window_s=1.5)` reads `[input]`, the mouse-move wake threshold, the same way. Each value must be a positive, finite number.
- `projector_match(config_path=WHITEBOARD_CONFIG) -> str` reads the whiteboard's `[display] name_match`, so both tools pick the same projector. It falls back to `"PROJ-1"`, and logs a warning if the file is unreadable or the key isn't a string.

## Depends on

The standard library only (`tomllib`).
