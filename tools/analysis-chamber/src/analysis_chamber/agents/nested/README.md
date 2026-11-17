# agents.nested

Schema-held sub-agent sessions the chamber tools run on `config.fetch_model`:

- `SdkExtractor`: tool-less, bounded by `EXTRACT_TIMEOUT_S`.
- `SdkSearcher`: WebSearch only, under `bypassPermissions`. It fails on a permission denial or when no results are left.
- `SdkSignup`: browser plus signup-account mail reads. It writes the key to `.env` via `append_env_var` once `is_allowed_env_var` passes, deletes the session's CLI transcript afterwards (`delete_session`, injectable for tests), and never raises.

Each output is re-checked in Python (`check_extract`, `check_results`) before anything reaches the lead, and failures raise `NestedError`. `SESSION_ENV` is the env every chamber session gets. See [../README.md](../README.md). Depends on `security`, `agents.runner`, `signal-untrusted`, `signal-jsonstate`.
