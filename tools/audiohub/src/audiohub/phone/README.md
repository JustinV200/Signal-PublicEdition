# audiohub.phone

The phone bridge behind `audiohub run --phone`. The owner pairs the glasses with their phone and opens a page there. The page streams the phone mic to the hub on this PC and plays the hub's speech, so Whisper, Kokoro, Claude, the kernel and every MCP tool run here while the owner is anywhere. Tailscale Serve carries the phone's HTTPS to a server on 127.0.0.1. Setup is in `tools/audiohub/PHONE.md`.

```
phone mic -> page (16 kHz int16) -> /ws -> PhoneLink -> RemoteFrameSource -> Hearing ...
... VoiceOutput -> RemoteSpeaker -> PhoneLink -> /ws -> page (WebAudio) -> glasses
```

## Public API (`from audiohub.phone import ...`)

- `PhoneLink()`: the one phone WebSocket.
  - A newer socket replaces the old one, which is closed with `REPLACED_CLOSE_CODE` (4000) so that page stops reconnecting.
  - Replays the mic state and the last status to each new socket.
  - `show_status(label, detail)` is the `StatusLine(on_show=...)` hook that mirrors the console status to the page.
  - `is_connected`. Use it from the event loop thread.
- `RemoteFrameSource(link)`: a `FrameSource` (see `loop/hearing`). It yields float32 frames of exactly 512 samples at 16 kHz, whatever size the page's chunks are. Setting `paused` also tells the page to stop sending. Only half-duplex (`audio.barge_in = false`) sets it; with barge-in the page streams the whole time.
- `RemoteSpeaker(link)`: the `play` / `stop` interface `VoiceOutput` uses.
  - `play` sends the chunk and returns when the page acks it.
  - Raises `AudioStreamError` if no phone is connected, if the phone drops or is replaced, or if no ack arrives within the duration plus `ACK_DEADLINE_MARGIN_S` (5 s).
  - The page acks 0.3 s before the end, so the next sentence queues without a gap. The echo tail covers that lead.
- `PhoneServer(link, phone_settings, token_path=DEFAULT_TOKEN_PATH)`: the aiohttp server. Use it as `async with`, or call `start()` / `close()`. It has `port` (0 picks a free one) and `token`.
- `phone_link_lines(phone_settings, token)`: what `run --phone` and `phone-link` print.
- `DEFAULT_TOKEN_PATH` (`.cache/phone-token`), `COOKIE_NAME`, `session_cookie_value(token)` and `FrameError`.

## Security

Any local web page can reach 127.0.0.1, and Tailscale Serve forwards to it, so:
- **Token.** `start()` writes `secrets.token_urlsafe(32)` to `.cache/phone-token`, owner-only, using the kernel's token helpers, and `close()` deletes it. A new run means a new token, so reopen the link after a restart.
- **Cookie.** `GET /?token=T` with the right token sets the `audiohub_phone` cookie (HttpOnly, Secure, SameSite=Strict, path `/`) and redirects to `/`.
  - The cookie holds an HMAC-SHA256 of the token, never the token itself.
  - The redirect is a meta refresh, not a 303, because a SameSite=Strict cookie isn't sent on a 303 in a navigation that began on another site, such as tapping the link in webmail.
  - Every other route (the page, its scripts, `/ws`) needs the cookie, compared in constant time.
- **Host and Origin.** Every request's Host must be `localhost`, `127.0.0.1` or a `[phone] allowed_hosts` name, which blocks DNS rebinding. The `/ws` handshake's Origin must be one of those names too, over `https` (or `http` for localhost), and must be the page's own origin, port included, because cookies and SameSite ignore ports.
- **Refusal.** A refused request gets a 403 and its connection is closed. Every request is refused while the server has no token (before start, or while stopping).
- **Socket limits.** One phone at a time. Messages are capped at 32 KiB (aiohttp closes with 1009), and the first message that breaks the protocol closes the socket with 1008. Pings every 10 s drop a phone that went to sleep. Request bodies over 1 KiB are refused.
- **Logging.** aiohttp's access log is off, because it would print the token link.
- **Page headers.** CSP `default-src 'self'` (no external resources), `Referrer-Policy: no-referrer` and `Cache-Control: no-store`.

## Wire format (`protocol.py`)

| Direction | Type | Content |
|---|---|---|
| phone to hub | binary | mic, int16 LE mono 16 kHz, 1 B to 32 KiB, even length |
| phone to hub | text | `{"type":"played","id":N}` |
| hub to phone | binary | `<uint32 id><uint32 sample rate>` LE, then int16 LE mono PCM |
| hub to phone | text | `{"type":"mic","on":bool}`, `{"type":"stop"}`, `{"type":"status","label":..,"detail":..}` |

## The page (`page/`)

- `index.html` has a big Start/Stop button and a status line (listening, thinking, speaking, ...).
- `app.js`:
  - opens the mic with `getUserMedia` (echo cancellation and noise suppression on)
  - holds the Screen Wake Lock, and takes it back when the page is visible again
  - reconnects with backoff from 1 s to 15 s, and after 4 failures suggests the link may be stale
  - drops mic audio while the hub says the mic is off (half-duplex only)
- `mic-worklet.js` is an AudioWorklet. It low-passes at 7 kHz (two biquads), downsamples to 16 kHz with linear interpolation, and posts 1024-sample int16 chunks.
- `player.js` queues each speech chunk behind the last on one `AudioContext`. It acks a chunk 0.3 s before it ends, and `stop` cuts everything.

## Files

| File | Contents |
|---|---|
| `link.py` | `PhoneLink` |
| `frame_source.py` | `RemoteFrameSource` |
| `speaker.py` | `RemoteSpeaker` |
| `server.py` | `PhoneServer`: lifecycle, routes, guard middleware, login |
| `socket_handler.py` | the `/ws` message loop |
| `auth.py` | cookie HMAC, Host and Origin checks |
| `protocol.py` | wire format, size caps, `FrameError` |
| `page_links.py` | `phone_link_lines` |
| `page/` | the phone page (HTML, JS, AudioWorklet) |

## Dependencies

- `aiohttp`, for the HTTP and WebSocket server.
- `numpy`.
- Inside audiohub, all through their entry points:
  - `audiohub.config` (`PhoneSettings`, `CACHE_DIR`)
  - `audiohub.kernel` (the token helpers)
  - `audiohub.audio` (`FrameChunker`, `AudioStreamError`)
  - `audiohub.stt` (`FRAME_SAMPLES`)
- Nothing imports `audiohub.loop`. The source and speaker meet its protocols structurally, and the CLI wires them in through `HubIo`.
