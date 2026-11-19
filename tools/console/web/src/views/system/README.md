# views/system

The System page (`Ctrl+6`; `Ctrl+7` and `Ctrl+8`, which opened Models and Tools before they moved here, stay aliases). Under the `SYSTEM` header, six groups:

- YOU: `devices`' `AwayControl` (Here / Away / Asleep with the `until` box and `I'm away`, or `I'm back`). The title row shows the same state while not Here.
- CONSOLE (`ConsoleSection.tsx`): the console's own checks (`GET /api/health`, read into the store by `app`'s `useConsoleHealth`) through `setup`'s `HealthList`, the same list TOOLS uses: counts in the header (`11 ok · 1 needs a look · 0 not working`) and `Check again`; no row button, a not-ok row shows its fix and command with Copy. The other-checkout case is the port row's own, with that checkout's path.
- TOOLS (`ToolsSection.tsx`, formerly a tab of its own): every registry tool's health from `setup status --json` through `setup`'s `ToolHealthList` (the `HealthList` rows with each tool's button), with `Check again`, `Open setup`, and each row's `Set up` / `Continue setup` / `Fix` / `Re-run setup` (opens the wizard at that tool; `Fix` carries the check, which leads the tool page) or `Add to Claude Code` (runs `setup wire` here, then the restart line). A tool setup has no record of that the CLI finds working and in Claude Code's config reads `Active` like a finished one, its words ending `found already set up`.
- DEVICES: `devices`' `DevicesMeta` in the header, then its `DeviceList` (the rows, `Open camera` and the camera panel).
- MODELS (`ModelsSection.tsx`): `models`' `ModelStrip` (the Claude and Voice pickers); while the Session hook check isn't ok, its header says the console can't see which model runs for that reason and `Show the Console row` scrolls to that row and focuses it.
- APPEARANCE (`AppearanceSection.tsx`): `now: dark` or `now: light` in words, then `Dark` and `Light`; the one in use is off with the quiet reason `in use now`. The theme lives on `<html>` (`state`'s `currentTheme` / `setTheme`), so a `theme` command shows here too.

`SystemView` holds the one `useDevices` poll that YOU and DEVICES share, so the poll runs only while System is open (and stops while the page is hidden). Each group header is `Section.tsx`: the shared `.view-header` line with an `h2` HUD title, its words, and its buttons on the right; `system.module.css` spaces the groups.

Public API: `SystemView`. Depends on `api`, `state`, `ui`, `models`, and the `devices` and `setup` views through their `index.ts`.
