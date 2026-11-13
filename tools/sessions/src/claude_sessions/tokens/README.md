# tokens

Shared-secret token files for loopback IPC. Used by the daemon (its own token in `.state/token`) and by the CLI and MCP server, which read it back. The voice hub's token is read by `signal_hub_notify` (`packages/hubnotify`).

- `create_token_file(path)`: writes a fresh `secrets.token_urlsafe(32)`. The file is restricted to the current user first: `icacls` on Windows, `0o600` elsewhere.
- `read_token(path)`: the token, or None when the file is missing, unreadable or empty.
- `tokens_match(given, expected)`: a constant-time comparison with `hmac.compare_digest`.

Depends on: the standard library only.
