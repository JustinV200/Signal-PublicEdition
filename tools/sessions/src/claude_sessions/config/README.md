# config

Settings for the whole tool, plus its fixed file locations.

- `Settings`: repo roots and depth, daemon and hub addresses, state folder, approval timeout.
- `load_settings(environ=None)`: defaults plus validated `SESSIONS_*` environment overrides. Raises `SettingsError`.
- `TOOL_ROOT`, `sessions_file(state_dir)`, `daemon_log_file(state_dir)`: where `.state/` files live.

Depends on: the standard library only.
