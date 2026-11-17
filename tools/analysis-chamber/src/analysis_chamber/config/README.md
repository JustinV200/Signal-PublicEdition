# analysis_chamber.config

Loads `tools/analysis-chamber/config.toml` (optional, gitignored, per-machine overrides) over the code defaults. Every key and its default is in [config.example.toml](../../../config.example.toml).

## Public API

- `load_config(path=None) -> ChamberConfig`: `None` reads `tools/analysis-chamber/config.toml`; a missing file means all defaults. Unknown keys and bad values raise `ConfigError`.
- `ChamberConfig` (frozen): `max_parallel_runs`, `critic_rounds_max`, `lead_model`, `critic_model`, `qa_model`, `fetch_model`, `signup_mail_account` ("" = API-key signup off), `repo_root`, `analyses_root`, `private_root`, `kit_venv`, `log_dir`, `state_dir`, `playbook_path`. Paths are absolute.
- `TOOL_DIR`, `REPO_ROOT`, `DEFAULT_CONFIG_PATH`.

Path values expand environment variables (`%VAR%`, `$VAR`, `${VAR}`) and resolve against the repo root when relative. A variable that isn't set raises `ConfigError` instead of leaving the literal text in the path. `repo_root` comes from where the tool lives and isn't configurable.

## Depends on

The standard library only.
