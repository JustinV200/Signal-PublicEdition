# actions

The console's buttons, run directly by the console server: no request to the orchestrator, no Claude turn.

- `plans.py`: `plan_action(action, args, saves)` checks a click and returns an `ActionPlan(display_text, lock, step)`, or raises `ActionError`. `board.load` and `board.update` names must be in the whiteboard's current save list; `board.update` also needs the save's `refresher` (`tasks` or `todo`) or `{view: "todo"}`. Voice actions share the `voice` lock and board actions the `board` lock. A save name in `display_text` (`Send to projector: "lecture"`) is JSON-quoted with every letter as typed (non-ASCII too), and quotes, newlines, controls, bidi and other invisible characters (format characters by category, plus `_INVISIBLE_RANGES`, an explicit list of default-ignorable ones such as Hangul fillers and variation selectors, shared with the page) escaped as `\uXXXX`, so a name can't pass for the words around it; the page's `quoteName` (`web/src/state/actions/actionLabels.ts`) gives the same text.
- `steps.py`: `run_step(step, state_dir, tools)` runs it and returns the words to show, or raises `StepFailed`. `ActionTools` holds the functions it calls, so tests pass fakes.
- `whiteboard_cli.py`: `run_whiteboard(args)` runs `uv run --env-file .env --project tools/whiteboard --frozen --no-sync whiteboard <args>` (as `.mcp.json` does) from the repo root as an argument list (no shell, no window, Claude session variables removed), with a 110 s timeout. A non-zero exit raises `StepFailed` with the CLI's `whiteboard: error:` line, or its own failure line. On the timeout, or when the action is cancelled (server shutdown), it kills the CLI's own process tree (`process_tree`) and reaps it, but never a whiteboard daemon the CLI just started (`... -m whiteboard.cli serve`), which is meant to outlive it.

What each action runs:

| Action | Runs |
| --- | --- |
| `voice.start` | `hub.start_hub` (refuses while a hub runs) |
| `voice.stop` | `hub.stop_hub` (asks the hub to exit cleanly, then kills only the hub's own processes if it hasn't after 10 s) |
| `board.load NAME` | `whiteboard load --no-ink -- NAME` |
| `board.todo` | `whiteboard todo show` |
| `board.idle` | `whiteboard idle show` |
| `board.realign` | `whiteboard realign` |
| `board.calibrate` | `whiteboard calibrate` (the page confirms first) |
| `board.update` | `whiteboard tasks show` (refresher `tasks`) or `whiteboard todo show` (`todo`); never the old save. The page's `Show live version`; over a drawing it confirms first unless the refresher is `todo` |

The whiteboard CLI starts its daemon if it's down, as the `board_*` tools do.

Public API: `signal_console.actions`. Depends on `psutil`, `hub`, `launch`, `paths` and `process_tree`.
