# views/devices

The devices package, which System composes into its YOU and DEVICES groups: everything Signal uses and its live state, from `GET /api/devices` (polled every 5 s while System is open and the page is visible, and re-read at once on the status line's Refresh button).

- `useDevices.ts`: the polling hook. Only System mounts it, so the poll runs only while System is open; it stops while the page is hidden.
- `DevicesMeta.tsx`: the DEVICES header's words, only when they matter: `Not updating: <why>`, `checking…`, or `updated 20s ago` once the last read is past 15 s.
- `DeviceList.tsx`: the device rows, and the camera panel while it's open.
- `DeviceRow.tsx`: `● Projector  Projecting a drawing`. Each row has a shape (`ui`'s disc on, ring off, a text `?` unknown) and the server's words, which say the state (no separate state word); a row that isn't on sets its words in 600; colour is only a third cue. The rows are the projector and webcam (the whiteboard daemon's status), Voice, the desktop browser and Docker for the docker browser.
- `CameraPanel.tsx`: the webcam's live view on a `.panel`, through the console's camera proxy (`api`'s `openCameraStream`). It closes the stream when it unmounts (Close camera, or leaving System), which frees the whiteboard's viewer slot. The server's errors (2 viewers already, no picture, whiteboard off) show as they come, in words. Opening it is a read: nothing goes to Claude.
- `AwayControl.tsx`: the owner's Here / Away control (System's YOU). `Here` / `Away until Thu 17:00` / `Away (ends by itself in 3 days)` / `Asleep (sleep mode)` (`status`' `awayWords`), with the labelled `until` box (a weekday, `tomorrow` or a date; caption `Empty = 3 days.`; Enter submits) and `I'm away`, or `I'm back`. It's the owner's own switch, so it calls `POST /api/away` directly instead of asking Claude.

Public API (`index.ts`): `useDevices`, `DevicesMeta`, `DeviceList`, `AwayControl`. Depends on `api`, `state`, `status` (the away words), `time` and `ui`.
