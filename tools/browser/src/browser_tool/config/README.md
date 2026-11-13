# browser_tool.config

Settings for the browser tool: frozen dataclasses with defaults in code, an optional TOML override file, and the tool's well-known paths.

## Public API (`from browser_tool.config import ...`)

- `load_settings(path: Path | None = None) -> Settings`
  - With `None`, reads `DEFAULT_CONFIG_PATH` (`tools/browser/browser.toml`, gitignored) if it exists, otherwise returns defaults.
  - An explicit path must exist.
  - Raises `ConfigError` (a `ValueError`) on invalid TOML, unknown sections or keys, wrong types, non-positive numbers, gate patterns that don't compile, unknown `always_confirm` categories, a `[duo] site_names` entry whose key isn't an exact lowercase hostname or whose name isn't letters, digits, spaces, dots and hyphens (at most 40 characters), and a `[duo]` hub address that isn't a loopback IP with a port up to 65535 (the hub's token goes with every note).
- `settings_from_dict(data, source)` validates an already-parsed mapping (used by tests).
- `Settings` has seven sections: `browser` (`BrowserSettings`), `policy` (`PolicySettings`), `gates` (`GateSettings`), `duo` (`DuoSettings`: the voice heads-up for Duo prompts, the Verified Push code relay and the owner's `site_names`), `downloads` (`DownloadSettings`: whether the desktop browser saves downloads, the folder and the size cap), `uploads` (`UploadSettings`: the folders `upload_file` may send files from, by default the repo's `life/` and `.downloads`, and the size cap) and `visit` (`VisitSettings`: visit mode's login and sign-in rules, ignored by the MCP server). Lists become tuples; `site_names` stays a dict. `[visit] login_host`, `login_credential` and `login_from_hosts` must be set together or not at all. An `[uploads]` root, the `[downloads]` folder or `[browser] cookie_file` on a UNC share or mapped network drive (`paths.is_network_path`) is a config error.
- Host patterns (`[policy] allow`/`deny`, `[duo] code_relay_sites`) are only type-checked here. Their form is checked by `browser_tool.policy` when `ActionContext.create` (and its `DuoWatch`) is built, which `main` reports as a config error, so this package stays free of other browser_tool imports.
- `CATEGORY_PATTERNS`: the `[gates] always_confirm` categories (`CATEGORY_PURCHASE`, `CATEGORY_SEND`, `CATEGORY_DELETE`) and their built-in regexes. `ALL_CATEGORIES` is the default list. Retired names (`password_submit`, `grant_access`) in `always_confirm` are dropped with one warning each, so older files still load.
- `TOOL_ROOT` is `tools/browser`; `resolve_tool_path(value)` makes a config path absolute against it.

Every key and its default is documented in `tools/browser/browser.example.toml`.

## Files

- `paths.py`: path constants and `resolve_tool_path`. They assume uv's editable install.
- `settings.py`: section dataclasses and defaults.
- `confirm_categories.py`: the always-confirm categories and their patterns.
- `loader.py`: reads TOML, checks types, builds `Settings`.

## Dependencies

Standard library only. Imports nothing else from browser_tool.
