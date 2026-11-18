# analysis_chamber.phases

The run's agent work: the plan, then collect, analyse, critique and report, and Q&A over the run folder. The contract is in [../../../DESIGN.md](../../../DESIGN.md).

## Public API

`from analysis_chamber.phases import ...`

- `PhaseAgents(runner, options)`: an `AgentRunner` and an `AgentOptionsFactory` (`lead(ctx)`, `plan(ctx)`, `critic(ctx)`, `qa(ctx, resume, fork)`).
- `PipelineHooks(notifier, on_update, kit)`: an async `on_update(manifest)` the daemon uses to persist and report progress, the `Notifier` (`done` / `closed`) and a `RunKit` (`make_run_venv`, idempotent and called every run, and `list_installs`, both run via `asyncio.to_thread`; the `analysis_chamber.kit` module fits).
- `async draft_plan(ctx, agents) -> str`, `async revise_plan(ctx, agents, edits) -> str`: write `plan.md` and `manifest.plan_text`. They use the plan options (no MCP servers), so they can't collect anything; the plan prompt lists what collect can use via `agents.options.collect_tools(ctx)`.
- `async run_pipeline(ctx, agents, hooks) -> None`: runs the phases not in `finished_phases`. Failure is recorded (status failed, `last_error`, partial `outputs`, `closed`) and not raised; cancellation is recorded and re-raised.
- `async ask(ctx, agents, question) -> str`: answers, flags partial results mid-run, and appends to `qa.md`.
- `PhaseError`: an agent turn failed or a phase left out a required file.

## Rules

- Phases mutate `ctx.manifest`. `run_pipeline` awaits `on_update` on every change; for the other calls the caller persists after they return.
- Sessions are stored as `sessions[role]` plus `sessions[role + "_cwd"]`. A session is only resumed from the folder it was made in. Otherwise, or when resume errors, a fresh session gets a summary of the run folder (from the session-resume spike).
- The critic is a fresh session every round. `critique.md` is written by this package from each round's findings and the lead's resolution table.
- Only `personal is False` keeps the `artifact` report format; anything else is recorded as `html`.
- The chamber tools append their own source records to `manifest.sources`. The lead keeps `sources.json` for the rest (Signal reads, named files), merged in by url after collect and before the report, and `results.md`. Marker lines in replies: `REPORT_FORMAT:`, `TOP_FINDING:`, `NO_FINDINGS`.
- Prompts are the `prompts/*.md` templates (`string.Template`).

## Depends on

`config`, `runs`; `agents` and `notify` for types only (injected).
