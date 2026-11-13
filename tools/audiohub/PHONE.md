# Phone bridge setup

Use the full voice assistant from anywhere: the glasses pair with your phone, and a page on the phone sends your voice to audiohub on this PC and plays Claude's replies. Whisper, Kokoro, Claude, the kernel and every MCP tool still run on the PC. Tailscale provides private HTTPS between the phone and the PC.

## One-time setup

1. **Install Tailscale on the PC and on the phone, and sign in to the same account on both.**
   - PC: https://tailscale.com/download/windows
   - Phone: the Tailscale app from the App Store or Play Store.

2. **On the PC, publish the phone page to your tailnet.** In a terminal:

   ```
   tailscale serve --bg --https=443 http://127.0.0.1:8781
   ```

   - `--bg` keeps it on across reboots until you turn it off. `--https=443` serves it at `https://<pc-name>.<tailnet>.ts.net/` with a certificate Tailscale issues.
   - If Tailscale asks you to enable HTTPS certificates or MagicDNS for the tailnet, follow the link it prints and enable them.
   - `tailscale serve status` shows what is published and the exact URL. `tailscale serve --https=443 off` stops publishing it.
   - Only your own tailnet devices can reach it. This isn't Tailscale *Funnel*, which would publish to the public internet, so don't use Funnel for this.

   *Syntax source:* the Tailscale Serve CLI reference, https://tailscale.com/kb/1242/tailscale-serve, which gives `tailscale serve [flags] <target>`, `--bg`, `--https=<port>`, `status` and `off`. **Flag:** that page's examples use targets like `localhost:3000`. The exact line above, with the `http://127.0.0.1:8781` target, is put together from its rules rather than copied from an example. If your Tailscale version rejects it, use the documented form `tailscale serve --bg localhost:8781`, then check `tailscale serve status`.

3. **Tell audiohub the PC's Tailscale name.** Take the host name from the URL that `tailscale serve status` shows, for example `pc-name.tail1234.ts.net`. Put it in `tools/audiohub/audiohub.toml`:

   ```toml
   [phone]
   allowed_hosts = ["pc-name.tail1234.ts.net"]
   ```

   The page refuses any other host name, so this step is required.

4. **Pair the glasses with the phone.** Disconnect them from the PC first if they connect there automatically. They must be the phone's current audio output and input.

## Every time

5. **On the PC, from `tools/audiohub`, run:**

   ```
   uv run audiohub run --phone
   ```

   It prints two links, both with a fresh secret token:

   ```
   phone: on this PC: http://127.0.0.1:8781/?token=...
   phone: on the phone: https://pc-name.tail1234.ts.net/?token=...
   ```

   `uv run audiohub phone-link` prints them again while the hub runs.

6. **On the phone, open `https://<pc-name>.<tailnet>.ts.net/?token=...` and tap Start.** Allow the microphone when asked, then talk as usual ("Hey Claude, ...").
   - The link sets a login cookie and drops the token from the address bar, so later you can open `https://<pc-name>.<tailnet>.ts.net/` directly, until the hub restarts.
   - To get the link onto the phone, send it to yourself, for example in a note-to-self. Treat it like a password: anyone on your tailnet who has it can talk to Claude with your tools.

## Known limits

- **The screen must stay on, with the page in front.** The page holds a screen wake lock (iOS 16.4+, recent Android Chrome). If the screen locks or you switch apps, the phone stops the mic and the connection. Come back to the page and it reconnects by itself. If the browser can't hold the wake lock, the page says so; turn auto-lock off instead.
- **Latency.** Your voice and Claude's replies cross the network, so expect about 0.1 to 0.5 s more each way than at the PC, more on a weak mobile signal. There can be a short pause between sentences.
- **Barge-in works as at the PC.** With `[audio] barge_in` on (the default) the page keeps the mic on while Claude speaks, so you can say "stop" or "Hey Claude, ..." over it. While Claude is still playing, the hub drops what merely repeats its sentences from the last `[phone] echo_tail_s` (2.5 s, longer than at the PC because the network adds lag) plus a 1 s margin; once you could have heard it stop (`[audio] reply_after_s` after its audio ends, plus the phone's extra lag, `[phone] echo_tail_s` minus `[audio] echo_tail_s`: 1.8 s by default), only an echo of its last words is dropped, so quick replies get through. The phone browser's own echo cancellation, which the page turns on, helps keep Claude's voice out of the mic. How well that works with Bluetooth glasses depends on the phone. With `barge_in = false` the page mutes the mic while Claude speaks and for 2.5 s after.
- **The PC must be on and awake**, with `audiohub run --phone` running and Tailscale connected. Set Windows not to sleep while you use it.
- **A new token each run.** After the hub restarts, the page can't reconnect. It suggests opening the new link from `audiohub phone-link`.
- **One phone at a time.** Opening the page somewhere else takes over, and the older page stops.
- **Ducking still applies to the PC's Spotify**, not to music on the phone.
