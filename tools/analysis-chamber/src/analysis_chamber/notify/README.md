# analysis_chamber.notify

Progress and done notices for a run (spec 7.8). Contract: [../../../DESIGN.md](../../../DESIGN.md).

## Public API

`Notifier(config, run=..., append_brief=..., hub=...)`, all methods `async`:

- `progress(manifest)`: console Tasks page (`console tasks set chamber-<id> ...`, name `Chamber: <question>` or `Chamber: personal run` unless `personal is False`; ids over 40 characters get a hash suffix; status `queued` or `building`, `--next` is the phase). Skipped when phase, percent and status are unchanged since the last call.
- `done(manifest, top_finding, report_path)`: brief entry, voice ping, then `console tasks done`. The finding appears in the brief and voice only when `manifest.personal is False`; personal (or unanswered) runs say "see the run folder".
- `closed(manifest)`: failed or cancelled; only `console tasks rm` (not `done`, which would show 100%).

A failing channel is logged with the run id and never stops the others or raises.

## Depends on

`config`, `runs`, `signal_brief`, `signal_hub_notify`. The console CLI runs from `config.repo_root`. The hub address is a constant (127.0.0.1:8765, token from audiohub's `.cache/ipc-token`).
