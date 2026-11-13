# browser_tool.credentials

The contract with the vault (`tools/vault`, package `vault`). The vault fills login forms itself, in-process. No secret ever crosses this interface or reaches the model.

## Public API (`from browser_tool.credentials import ...`)

- `LoginFiller` (Protocol):
  - `list_credentials() -> list[CredentialInfo]`
  - `async fill_login(page, credential_id, *, submit=False) -> FillResult`
  - `async has_filled_fields(page) -> bool`. While True, `snapshot()` and `screenshot()` refuse.
  - `scrub(page, text) -> str`. It runs over every tool result.
- `CredentialInfo(id, label, origins, username_hint)` holds metadata only. `FillResult(ok, reason)` holds the outcome.
- `VaultUnavailableError` is raised by credential calls when there is no usable vault.
- `LazyVaultFiller()` imports `vault` on first use and delegates to its module-level functions.
  - If `vault` isn't importable, or lacks the four functions, it falls back to `MissingVaultFiller`.
  - `MissingVaultFiller` makes `list_credentials` and `fill_login` raise `VaultUnavailableError("vault not installed")`.
  - The docker server (`--backend docker`) uses `MissingVaultFiller("vault fills are off in docker jobs")` directly, so the vault is never imported.
  - Its `has_filled_fields` returns False and its `scrub` returns the text unchanged.
- `format_fill_result(result)` returns `"ok"` or `"failed: <code>"`. A reason that isn't a short `[a-z0-9_]` code becomes `error`.
- `format_credentials(list)` returns one line per credential.

## Enabling the vault

Add `tools/vault` as a uv path dependency of this project:

```
uv add --editable ../vault
```

## Files

- `types.py`: the protocol, data types and error.
- `missing_vault.py`: the no-vault fallback.
- `vault_loader.py`: the lazy import and module adapter.
- `formatting.py`: the model-facing text.

## Dependencies

Standard library only. The vault is optional and imported lazily.
