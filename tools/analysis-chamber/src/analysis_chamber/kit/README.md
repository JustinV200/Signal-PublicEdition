# analysis_chamber.kit

Builds the shared analysis kit venv (CUDA torch plus the pinned stack) and per-run venvs layered on it. (The original CUDA-kit notes are not published.)

## Public API

- `KIT_REQUIREMENTS`, `KIT_TORCH`: paths to the pinned files in `requirements/` (full freeze minus torch; torch plus the cu132 index).
- `build_kit(config)`: torch from the CUDA index first, then `uv pip sync` of `<kit>/kit-sync.txt` (torch pin plus the rest, so dropped pins are removed); writes `<kit>/kit-constraints.txt`. Idempotent (a stamp of the pins' hash).
- `make_run_venv(run_dir, config) -> Path`: `run_dir/.venv` with a `.pth` pointing at the kit.
- `run_env(run_dir, config) -> dict`: `VIRTUAL_ENV`, `PATH` (run venv Scripts, then the tool venv Scripts where `analysis-chamber.exe` lives, then the old PATH), `JUPYTER_PATH`, `CHAMBER_KIT_CONSTRAINTS` and `UV_CONSTRAINT` (both the kit constraints, so a stray plain `uv pip install` cannot pull CPU torch) and `CHAMBER_ENV_FILE` (`<repo_root>/.env`, where `chamber_get_api_key` appends API keys) for the lead's session.
- `list_installs(run_dir, config) -> list[dict]`: `{package, version}` in the run venv and not (same version) in the kit.
- `install_into_run_venv(run_dir, config, packages, allow_shadow=False) -> list[dict]`: resolves with `uv pip compile` against the kit constraints (cu132 index added), installs with `--no-deps` only what the kit lacks at that version, refuses to replace a kit package unless `allow_shadow`; torch is never shadowed. It uses `unsafe-best-match` with the cu132 extra index (safe: kit packages are exactly pinned). Raises `KitError` if the kit is not built. Returns what it installed (CLI: `analysis-chamber install`).
- `KitError`: a uv call failed. Every kit uv call (`run_cmd`) drops `UV_CONSTRAINT` from its env, so the lead's guard never applies to the kit's own constrained installs.

To change a pin, edit `requirements/` and rebuild; the stamp changes and `build_kit` reinstalls.

Depends on: `config`, `uv` on PATH.

UV_CONSTRAINT also holds `uvx` tools to the kit versions.
