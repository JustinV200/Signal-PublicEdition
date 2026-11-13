# mail_tool.config

Where the mail tool keeps its files, and its one setting.

## Public API

- Paths: `TOOL_ROOT`, `REPO_ROOT`, `STATE_DIR` (`tools/mail/.state/`, gitignored), `CLIENT_SECRETS_PATH` (`.state/google_client.json`), `ACCOUNTS_DIR` (`.state/accounts/`), `CONFIG_PATH` (`.state/mail.toml`).
- `Settings(send_confirm=True)` and `load_settings(path=CONFIG_PATH)`. The file is optional; an unknown section or key raises `SetupError`.

```toml
[send]
confirm = true   # false sends drafts without the owner's Allow/Deny dialog
```

## Depends on

The standard library, and `mail_tool.errors`.
