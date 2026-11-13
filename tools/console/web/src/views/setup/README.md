# views/setup

The setup wizard (`Ctrl+9`, and where `setup` / `/setup` open the console with `#v=setup`). Every action runs one fixed command of the setup CLI (`tools/setup`) through `POST /api/setup/run`, so the registry, settings schemas and `.setup/progress.json` stay the single source of truth, and the wizard resumes at the first unfinished tool.

- `SetupView.tsx`: the step strip, one screen at a time, Back and Next; where it starts (`wizardScreens.ts`: built from `setup list`, resumed from progress, or opened at a tool by the Tools page or `#t=`).
- `screens/`: Welcome (intro and missing programs), Pick tools (`setup choose`), one screen per picked tool, Permissions (`setup plan`, then `setup wire --yes`), Summary (health of the picks) and Tour (the console tour button and GUIDE.md a section at a time).
- `steps/`: a step's status (mark and word) and its controls by kind: Run, Yes/No (e.g. browser auto-approve), Mark done, a value field, the settings form, the samples panel, or Open a terminal for steps that take a secret.
- `settings/`: forms rendered from the settings schema (`setup config <tool> --list`), saved with `--set`; placeholders are flagged in words.
- `samples/`: copytone samples by paste, file paths or sent mail.
- `run/`: `useSetupRun` (one command with live output), `OutputLog` and `HandToClaude` (sends a failure to Claude in Chat, or copies it when no session has claimed the console).
- `health/`: tool health in words and the list the Tools page shares.
- `useSetupQuery.ts`: read-only commands (list, intro, plan, tour, status) loaded on open and on Refresh.

Public API: `index.ts`. Depends on `api`, `state`, `ui` and `markdown`.
