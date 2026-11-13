# views/devices

The Connected devices page (`Ctrl+6`): everything Signal uses and its live state, from `GET /api/devices` (polled every 5 s while the view is open and the page is visible, and re-read at once on the status line's Refresh button).

- `DevicesView.tsx`: header (`checked 5s ago`, or why it isn't updating), a hint, the Away/Here block, the device rows, and the camera panel while it's open.
- `DeviceRow.tsx`: `● Projector  on Projecting your board`. Each row has a shape (filled on, hollow off, `?` unknown), the state word and the server's words; colour is only a third cue. The rows are the projector and webcam (the whiteboard daemon's status), the voice hub and glasses (the hub status; the glasses follow the hub, which holds their mic), the desktop browser and Docker for the docker browser.
- `CameraPanel.tsx`: the webcam's live view through the console's camera proxy (`api`'s `openCameraStream`). It closes the stream when it unmounts (Close camera, or leaving the view), which frees the whiteboard's viewer slot. The server's errors (2 viewers already, no picture, whiteboard off) show as they come, in words. Opening it is a read: nothing goes to Claude.
- `AwayControl.tsx`: the owner's Away/Here toggle. `Here` / `Away until Thu 17:00` / `Asleep (sleep mode)`, with `I'm away` (and an optional until: a weekday, `tomorrow` or a date) or `I'm back`. It's the owner's own switch, so it calls `POST /api/away` directly instead of asking Claude.
- `useDevices.ts`: the polling hook.

Depends on `api`, `state`, `time` and `ui`.
