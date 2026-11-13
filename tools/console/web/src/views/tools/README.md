# views/tools

The Tools page (`Ctrl+8`): every tool in the setup registry with its live health from `setup status --json`, as a mark and a word (`● Active`, `✗ Down`, `○ Not set up`) plus what the check said. Each row's button (Set up, Continue setup, Fix, Re-run setup) opens the setup wizard at that tool. Check again re-reads; so does the status line's Refresh.

Public API: `ToolsView`. Depends on `api`, `state`, `ui` and the setup view's `HealthList` and `useSetupQuery`.
