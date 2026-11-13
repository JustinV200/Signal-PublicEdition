# console web

The front end of the Signal console: a radar-styled HUD onto the Claude Code orchestrator. A scope with the live state lands first; chat, voice, boards, tasks, devices, models, tools and setup are tabs beside it, with a status line above and an input line below. The spec is `DESIGN.md`.

Everything the page does goes through the backend in `tools/console/src`: typing sends `POST /api/send`, every button and palette command sends `POST /api/action`, and the page only reads state from `GET /api/state`, the `GET /api/events` stream (including the `tasks` event), `GET /api/devices` and the camera stream `GET /api/camera/stream`. The Devices page's Away/Here toggle calls `POST /api/away` and the model pickers `POST /api/models`. The Setup and Tools pages run the setup CLI through `POST /api/setup/run` (streamed) and `POST /api/setup/terminal`. Typed messages go to Claude; buttons don't: the console server runs each one itself, so a button reads "Working…" and its action row in Chat goes working, then done with what happened (or failed with why). All server text is rendered as React elements; nothing touches `innerHTML`.

The page keeps itself current: the server pushes every change on the stream (a keepalive every 5 s when idle), the page reopens a stream that goes 20 s without a byte, and it re-reads everything when the window becomes visible again or the network returns. The status line says `updated 3s ago`, and its Refresh button re-reads now. After a server restart the page is signed out (tokens live in server memory), so run `console open` again.

## Commands

Node 24 (`C:\Program Files\nodejs`). From this folder:

- `npm install` once.
- `npm run build`: type-check, then write `dist/`, which the Python backend serves as static files.
- `npm test`: Vitest (markdown URL policy, reducer dedupe, 401 handling, board rows and Update, action progress from deliveries, the camera's MJPEG reader, the Tasks page's words, the event stream's stall reconnect and resync, the setup CLI's JSON in its output, settings schema to form fields, where the wizard resumes, tool health words).
- `npm run lint` (also refuses a UTF-8 BOM), `npm run format`.
- `npm run mock`: the fake backend on `127.0.0.1:8790` (`dev/mock-server.mjs`); `npm run mock -- --static dist` also serves the build, `--old-whiteboard` reports the whiteboard on with no view (the to-do button is then disabled), `--whiteboard-off` reports it off (no saves listed, every button on). The Tasks and Devices data come from `dev/mock-pages.mjs` (its camera always answers "2 viewers already"). Open `http://127.0.0.1:8790/#k=dev`.
- `npm run dev`: Vite with `/api` proxied to the mock. The real backend refuses proxied requests (Vite's Host/Origin), so test against it through `dist/`.

## Layout

```
src/
  main.tsx       fonts, styles, theme, render
  app/           App (session gate), Shell (status + view + input), SignIn (401)
  api/           wire types, parse checks, fetch client, SSE with backoff
  state/         reducer, dedupe, board rows and view words, session start, store
  state/actions  optimistic sending, action labels, action progress and the pending set
  status/        status line: connection words, freshness and Refresh, view tabs, help button, phase dot
  models/        the Models page: now / next-session pickers, voice's pickers
  help/          the help panel (what each view does, shortcuts) and the console tour bar
  ui/            the shared Button (hover/press/focus, pending, disabled with a reason), page visibility
  views/scope    the radar: blips and readout from the live state, the SVG scope
  views/chat     message stream, working row, dividers
  views/voice    voice state, Start/Stop buttons and the feed
  views/boards   board list, preview panel, Send to projector, Update, Realign and Full calibrate
  views/tasks    the orchestrator's task list and the usage line
  views/devices  device rows, the camera view and the Away/Here toggle
  views/tools    each tool's health (Active, Down, Not set up) and a button into setup
  views/setup    the setup wizard: screens, steps, settings forms, samples, live output
  input/         input line, history recall, auto-grow, confirm line
  palette/       Ctrl+K commands, filter, list
  keys/          global shortcuts
  markdown/      react-markdown with http(s)-only links and no raw HTML
  scroll/        auto-follow and the "N new" pill
  time/          clock formats and the shared ticker
  styles/        tokens (both themes), base, motion
tests/           mirrors src/
dev/             mock backend (not bundled)
```

Each `src/` folder has a `README.md` and an `index.ts`; folders import each other only through `index.ts`.
