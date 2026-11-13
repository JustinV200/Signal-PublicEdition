# api

Everything that talks to the console backend (`tools/console/src`) lives here, so a contract change touches one folder.

- `types.ts`: wire types for `/api/state`, SSE events (including `tasks`), send, action, `/api/devices` and `/api/away`.
- `parse.ts`: shape checks on every payload before it reaches the store; `parseTasks.ts` (the `tasks` event) and `parseDevices.ts` (devices and away) beside it, sharing the field checks in `parseFields.ts`.
- `token.ts`: the per-login token (memory plus `sessionStorage`) and the `X-Console-Token` header.
- `client.ts`: `login` (stores the token), `getState`, `sendText`, `sendAction`, `getDevices`, `setAway` (the owner's own Away/Here toggle); same-origin JSON; a 401 clears the token and throws `UnauthorizedError`.
- `sse.ts`: a `text/event-stream` parser for streams read with fetch.
- `events.ts`: `connectEvents(handlers)` reads `/api/events` with streaming fetch (EventSource cannot send headers), reconnects with 1/2/4/8 s backoff, and re-fetches `/api/state` before each reopen so a dead token becomes `onUnauthorized`. A stream with no bytes for `STALL_MS` (20 s; the server's keepalive is every 5 s) counts as dead and is reopened, and `onAlive` fires on every chunk. It returns `{resync, close}`: `resync()` drops the stream and reconnects at once.
- `camera/stream.ts`: `openCameraStream({onFrame, onError, onEnd})` reads `/api/camera/stream` with the page's token (the server adds the whiteboard's, so the page never holds it) and hands out each frame as a `blob:` URL; the returned function aborts the fetch, which ends the stream upstream. `camera/mjpeg.ts`: `createMjpegParser()` cuts the multipart body into JPEGs by each part's Content-Length.

Public API: `index.ts`. Depends on nothing else in `src/`.

`setup/` is the setup wizard's and the Tools page's side: `runSetup(request, onLine)` posts one fixed command to `/api/setup/run` and reads its NDJSON answer as it streams (`{"line"}` per output line, then `{"exit"}`); `openSetupTerminal(tool)` posts `/api/setup/terminal`. `types.ts` mirrors the setup CLI's requests and answers, `parse.ts` checks them, and `jsonDocs.ts` pulls the CLI's indented JSON documents out of its output lines (a step may print a program's own lines first).
