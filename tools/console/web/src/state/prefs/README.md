# state/prefs

The owner's preferences that outlast a page load, kept in localStorage, inside the `state` package. Every read and write is in try/catch, so blocked storage only means the default.

- `theme.ts`: the dark/light switch (`loadTheme`, `setTheme`); `currentTheme` reads the one on the page now (System's Appearance group).
- `tour.ts`: the console tour's stops in order (`tourStops(picks)`: Chat, Tasks, System, Scope, then Voice and Boards only when audiohub and the whiteboard are picked, both while the picks are unknown) and its last stop (`resumeTourStop`, `saveTourStop`), so the tour resumes where the owner left it.

Entry point: `index.ts` (re-exported by `state/index.ts`). Depends on `state`'s `types`.
