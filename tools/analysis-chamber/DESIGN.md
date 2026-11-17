# analysis-chamber design: the package contract

The original spec is not published. This file is the interface contract between the packages in `src/analysis_chamber/`. Each package is built by its own task against this file, so names here are exact. Import only from a package's entry point (`from analysis_chamber.runs import Manifest`), never from its internals.

Dependencies point one way: `config` and `runs` are the base; `guard` uses both; `gpu` and `kit` use `config`; `agents` uses `config`, `runs`, `guard`; `phases` uses `agents`, `runs`, `notify`; `daemon` uses everything below it; `mcp_server` and `cli` use `daemon` (its client).

Tests mirror the source: `tests/<package>/`. Shared fakes go in `tests/support/` (on `pythonpath`). Run them from `tools/analysis-chamber/` with `uv run --frozen pytest`, or from the repo root with `uv run --project tools/analysis-chamber --frozen pytest tools/analysis-chamber/tests/<package>`.

## Built: config

`from analysis_chamber.config import ChamberConfig, ConfigError, load_config, REPO_ROOT, TOOL_DIR, DEFAULT_CONFIG_PATH`

- `load_config(path: Path | None = None) -> ChamberConfig`. `None` reads `tools/analysis-chamber/config.toml` (optional, gitignored, per-machine overrides). A missing file means all defaults. The TOML is flat. Unknown keys, wrong types, ints below 1 and empty strings raise `ConfigError` (a `ValueError`).
- `ChamberConfig` is a frozen dataclass. Tests build variants with `dataclasses.replace(load_config(tmp_path / "missing.toml"), repo_root=..., ...)`.

| Field | Type | Default |
|---|---|---|
| `max_parallel_runs` | int | 3 |
| `critic_rounds_max` | int | 2 |
| `lead_model`, `critic_model`, `qa_model` | str | `"claude-opus-5-5"` |
| `fetch_model` | str | `"claude-sonnet-5-5"` |
| `signup_mail_account` | str | `""` (the one mailbox the signup agent may read; empty turns `chamber_get_api_key` off) |
| `repo_root` | Path | the Signal repo above `tools/analysis-chamber` (derived, not configurable) |
| `analyses_root` | Path | `<repo_root>/life/analyses` |
| `private_root` | Path | `%USERPROFILE%\analysis-chamber-private` |
| `kit_venv` | Path | `%LOCALAPPDATA%\analysis-chamber\kit` |
| `log_dir` | Path | `%LOCALAPPDATA%\analysis-chamber` |
| `state_dir` | Path | `<repo_root>/tools/analysis-chamber/.state` |
| `playbook_path` | Path | `<repo_root>/tools/analysis-chamber/skills/playbook` |

Path values expand environment variables (`%VAR%`, `$VAR`, `${VAR}`) and resolve against `repo_root` when relative; a variable that isn't set raises `ConfigError`. `KNOWN_KEYS` is the set of config keys. Every path is absolute. [config.example.toml](config.example.toml) lists every key with its default, and a test checks it loads to exactly the code defaults. A new key goes in `config/settings.py`, the example file and the table above in the same change.

## Built: runs

`from analysis_chamber.runs import ...`

- `Phase` (StrEnum): `PLAN="plan"`, `COLLECT="collect"`, `ANALYSE="analyse"`, `CRITIQUE="critique"`, `REPORT="report"`. `PHASE_ORDER: tuple[Phase, ...]` in that order.
- `Status` (StrEnum): `AWAITING_APPROVAL`, `QUEUED`, `RUNNING`, `DONE`, `FAILED`, `CANCELLED` (values are the lowercase names).
- `Manifest` (mutable dataclass). Only `id` and `question` are required:

| Field | Type | Default |
|---|---|---|
| `id` | str | required |
| `question` | str | required |
| `plan_text` | str | `""` |
| `personal` | bool \| None | `None` (until the user sets it at the plan check) |
| `phase` | Phase | `Phase.PLAN` |
| `status` | Status | `Status.AWAITING_APPROVAL` |
| `percent` | int 0-100 | 0 |
| `finished_phases` | list[str] (Phase values) | `[]` |
| `sessions` | dict[str, str] role -> SDK session id | `{}` |
| `installs` | list[{package, version}] | `[]` |
| `sources` | list[{name, url, status, note, fetched_at}] | `[]` |
| `timings` | dict[phase value, {started, finished}] | `{}` |
| `last_error` | str \| None | `None` |
| `outputs` | dict[name, path relative to the run folder] | `{}` |
| `report_format` | str \| None, one of `REPORT_FORMATS` = html, md, ipynb, artifact | `None` |
| `created_at`, `updated_at` | ISO-8601 UTC str | now |
| `queue_position` | int >= 0 \| None | `None` |
| `schema_version` | int | `SCHEMA_VERSION` (1) |

- `Manifest.to_dict() -> dict` (JSON-ready, enums as strings). `Manifest.from_dict(data) -> Manifest` raises `ManifestError` (a `ValueError`) on:
  - a non-dict, or a `schema_version` that isn't exactly the int 1 (the migration hook point);
  - an unknown or missing field, or a field of the wrong type (bools are refused for int fields);
  - an `id` that isn't a safe single path segment: lowercase alphanumeric words joined by single hyphens, the `make_run_id` charset;
  - a bad `phase` or `status` value, `percent` outside 0-100, a negative `queue_position`, or a `report_format` not in `REPORT_FORMATS`;
  - bad container items: `finished_phases` items must be Phase values; `sessions` and `outputs` map str -> str; `timings` maps phase values -> {str: str}; `installs` items are str -> str objects with at least `package` and `version`; `sources` items are objects with string keys.
- `read_manifest(run_dir: Path) -> Manifest`. Raises `ManifestError` if `manifest.json` is missing, unreadable, not JSON or invalid.
- `write_manifest(run_dir: Path, manifest: Manifest) -> Manifest`. Atomic (`signal_jsonstate.write_json_atomic`), sets `updated_at` to now, and **returns the written copy** without changing the argument. Raises `ManifestError`. Only one task may write a given run's manifest at a time (the temp file name is per process), so in the daemon each run's writes go through that run's own task.
- `make_run_id(question: str, today: date, taken: set[str]) -> str`: `<YYYY-MM-DD>-<slug>`, slug lowercase ASCII words joined by `-`, cut to 40 chars, `run` if empty; `-2`, `-3`, ... when taken.
- `create_run_dir(root: Path, run_id: str) -> Path`: makes `<root>/<run_id>/` with `RUN_SUBDIRS` (`data/raw`, `data/clean`, `extracts`, `code`, `figures`, `models`) and a `.gitignore` for `data/raw/ data/clean/ models/ .venv/ __pycache__/ .ipynb_checkpoints/`. Raises `FileExistsError` if it exists.
- `scan_runs(roots: list[Path]) -> list[tuple[Path, Manifest]]`: every `*/manifest.json` one level under each root, sorted by folder name per root. Missing roots are skipped; unreadable manifests, and manifests whose `id` isn't the folder name, are skipped with a logged warning.
- `move_run(run_dir: Path, dest_root: Path) -> Path`: moves the folder into `dest_root` keeping its name. Raises `FileExistsError` if the target exists.
- `utc_now_iso() -> str`, `MANIFEST_NAME = "manifest.json"`.

### Where a run lives

A new run (phase plan, `personal=None`) is always created under **`private_root`**, outside the repo, because the user hasn't said yet whether it's personal. At approval the daemon sets `personal` from the user's answer. If it's `False`, the daemon moves the run with `move_run(run_dir, config.analyses_root)` and calls `check_run_location` on the new folder. If it's `True`, the run stays in `private_root`. The daemon calls `check_run_location` before it writes into a run folder. The daemon never commits.

## Built: guard

`from analysis_chamber.guard import LeakError, can_publish, check_run_location, is_under`

- `check_run_location(manifest: Manifest, run_dir: Path, config: ChamberConfig) -> None`. Raises `LeakError` if `personal` is True or None and `run_dir` is under `repo_root` or not under `private_root`, or if `personal` is False and `run_dir` isn't under `analyses_root`.
- `can_publish(manifest: Manifest) -> bool`: True only when `personal is False` and `report_format == "artifact"`. The daemon's done result and the MCP status only offer a publish when this is True.
- `is_under(path: Path, root: Path) -> bool`: resolves both, then `is_relative_to` (WindowsPath compares case-insensitively). Use it for every path containment check, including `agents`' `personal_write_hook`.

## To build: gpu

- `gpu_lock(state_dir: Path, timeout_s: float | None = None) -> context manager`. Cross-process exclusive lock on `state_dir/gpu.lock` (msvcrt). Blocks until held; with a timeout, raises on expiry. The OS drops it when the process dies.
- CLI `analysis-chamber gpu -- <cmd...>` runs a command holding the lock and returns its exit code. The playbook tells the lead to wrap GPU steps in it.

## To build: kit

- `KIT_REQUIREMENTS`: the pinned analysis kit (pandas, polars, scipy, statsmodels, scikit-learn, xgboost, lightgbm, CUDA torch from its index, sentence-transformers, plotly, matplotlib, duckdb, ...).
- `build_kit(config: ChamberConfig) -> None`: builds or updates `config.kit_venv`.
- `make_run_venv(run_dir: Path, config: ChamberConfig) -> Path`: a run venv (`run_dir/.venv`) layered on the kit. Installs land only in the run venv.
- `list_installs(run_dir: Path, config: ChamberConfig) -> list[dict]`: `{package, version}` for packages in the run venv that aren't in the kit (for `manifest.installs`).

## To build: agents

- `RunContext` dataclass in `agents/context.py`: `run_dir: Path`, `manifest: Manifest`, `config: ChamberConfig`.
- Security: `DISALLOWED_TOOLS: list[str]`, every send, post, delete and draft-send tool across Signal's MCPs and the claude.ai connectors, plus `WebFetch` for the lead. PreToolUse hooks: `page_fetch_hook` (blocks Bash/Python fetches of HTML or text pages; data-file downloads allowed), `personal_write_hook` (personal runs can't write under `repo_root`; use `guard.is_under`), `send_block_hook` (second layer behind `DISALLOWED_TOOLS`).
- Option builders: `lead_options(ctx) -> ClaudeAgentOptions`, `critic_options(ctx)`, `qa_options(ctx, resume: str | None)`. All use `bypassPermissions` and always carry `DISALLOWED_TOOLS` and the hooks.
- In-process MCP server `chamber` for the lead with `chamber_fetch(url, instructions)` and `chamber_extract_file(path, instructions)`. Raw content goes only to a tool-less extractor on `config.fetch_model`; the lead gets the extract, also saved to `extracts/`.
- Runner: `AgentRunner` Protocol with `async run(options, prompt: str, resume: str | None = None) -> TurnResult`, where `TurnResult(session_id: str, text: str, is_error: bool)`. `SdkRunner` is the real one; tests use a fake.

## To build: phases

- `async run_pipeline(ctx, runner, notifier, on_update) -> None`: runs the remaining phases (collect, analyse, critique, report) after the ones in `manifest.finished_phases`, checkpointing the manifest with `write_manifest` after each. Critique runs up to `config.critic_rounds_max` rounds and writes `critique.md`.
- `async draft_plan(ctx, runner) -> str` and `async revise_plan(ctx, runner, edits: str) -> str`: the plan text (also written to `plan.md`).
- `async ask(ctx, runner, question: str) -> str`: Q&A; flags the answer as partial when the run isn't done; appends to `qa.md`.
- `on_update(manifest)` is called whenever the phase or percent changes.

## To build: notify

- `Notifier` with `progress(manifest)` (console Tasks page), `done(manifest, top_finding: str, report_path: Path)` (brief entry plus voice hub ping), `closed(manifest)` (failed or cancelled: closes the console task, no voice or brief).

## To build: daemon

- `analysis-chamber serve`. HTTP on 127.0.0.1, a random port, state file `state_dir/daemon.json` `{port, token, pid}` (owner-only). Constant-time token compare; the connection closes on the first bad request.
- JSON routes, all POST: `/start {question} -> {run_id, plan}`; `/approve {run_id, edits?, personal?} -> {run_id, status, plan?}` (edits revise the plan and keep it unapproved; approval needs `personal` set); `/status {run_id}`; `/list`; `/ask {run_id, question} -> {answer}`; `/cancel {run_id}`.
- At most `max_parallel_runs` active; the rest queue (`queue_position`). Interrupted runs resume on startup from their manifests (`scan_runs([analyses_root, private_root])`).
- `DaemonClient(state_dir)` with `start`, `approve`, `status`, `list`, `ask`, `cancel`, each returning a dict and raising `DaemonError` on failure.
- Rotating log in `log_dir`.

## To build: mcp_server

Five tools, thin wrappers over `DaemonClient`: `chamber_start`, `chamber_approve`, `chamber_status`, `chamber_list`, `chamber_ask`. Cancel is CLI only.

## To build: cli

`analysis-chamber serve | cancel <id> | start | approve | status | list | ask | gpu -- <cmd...> | mcp`. `cli.main(argv=None) -> int` is already the entry point (a stub that prints help).
