# audiohub

The central audio tool for Claude in this repo. It handles voice chat through the user's Bluetooth glasses, a Sonnet "kernel" that every user-bound message passes through, Spotify control, and music ducking while Claude speaks. Each package under `src/audiohub/` has its own README.

## Setup

Requirements:
- Windows 11
- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- A Claude Code login (`~/.claude`) or `ANTHROPIC_API_KEY`, for the voice session and the kernel.
- For GPU speech-to-text: an NVIDIA GPU. The CUDA 12 / cuDNN 9 DLLs come from the pinned `nvidia-*-cu12` wheels, so no system CUDA install is needed.

From `tools/audiohub`:

```
uv sync
uv run audiohub --help
```

Configuration is optional. Copy `audiohub.example.toml` to `audiohub.toml` (gitignored) and edit it. Every key is documented there, and unknown keys or wrong types are reported as errors.

## Quick start (the owner)

1. Connect the glasses. `audiohub.toml` points both devices at them by name:

   ```toml
   [audio]
   input_device = "BT-Glasses"
   output_device = "BT-Glasses"
   ```

   `uv run audiohub devices` shows what that resolves to.
2. From `tools/audiohub`, run `uv run audiohub run`. The first start downloads Whisper (about 1.6 GB) and Kokoro (about 340 MB).
3. Talk to Claude by starting with "Hey Claude", "Claude" or "Hey Signal", or by ending with ", Claude" or ", Signal" ("What's the time, Claude?"). A short two-tone chime says it heard the wake phrase (`audio.wake_chime`).
4. As soon as Claude finishes speaking, and for 8 seconds after you heard it end (`wake.follow_up_s`), you can reply without the wake phrase. Saying just "Hey Claude" opens the same window for your request.
5. Voice is a thin, fast layer and never asks for permission. It runs its own quick tools without asking: music, the whiteboard, the brief and todos, sleep mode, reading files, web search, and reading mail or a session's status (`brain.auto_allow_tools`, `brain.auto_allow_mcp_servers`). Anything else, such as code or file changes, running commands, browsing, sending mail or driving a session, is handed straight to the main Signal session (item 6): voice says one short line and passes the job on, and other tool calls are refused quietly. A hook makes Claude Code hand every tool call to the hub's permission gate, so nothing skips this check. Voice has no agent, scheduling or messaging tools (no SendMessage to your other sessions), and your claude.ai connectors (Gmail, Docs and the like) are turned off for it (`disableClaudeAiConnectors`); voice can search and read mail but never draft or send it. Secrets are never read: env files, token folders, the browser profile, `~/.ssh`, Claude Code, git, GitHub CLI, AWS, npm and Docker credentials, the vault store and your real browser profiles, cloud credentials and Claude Code's session transcripts are refused by path.
6. **Handing off to the main session.** For anything beyond its quick tools, Claude passes the job to your main Signal session, the orchestrator that last ran `console claim` (tools/console), straight away and without asking, saying one short line such as "Handing that to the main session." The message goes through the console's own sender (`packages/orchestrator`), starts with `[Signal voice]`, and carries your last few requests word for word as the hub transcribed them, kept apart from Claude's summary, plus a request that the main session tells you by voice when it's done or needs you. `[Signal voice]` is a label, never consent: anything holding that session's inbox token can write it, so the main session weighs the message on its content, and treats a summary that doesn't match your own words as suspect. If no session has claimed the console, or its inbox doesn't answer, Claude says the main session isn't reachable and you can type the job there. Details: `src/audiohub/brain/handoff_tool/README.md`.
7. "Claude, stop" cancels what Claude is doing and drops queued requests.
   While Claude is talking you can cut in: "stop" on its own works then, and "Hey Claude, ..." cuts it off and asks something new (`audio.barge_in`).
8. Ctrl+C stops the hub, and so does the console's Voice Stop, which asks it over IPC to shut down cleanly (music restored, audio closed) and kills it only if it hasn't exited after 10 s.
9. Notes from other agents (`notify`) are dropped, not spoken or queued, while you're asleep (sleep mode on) or away (the brief's away mode on). Your own conversation with the hub is unaffected. The hub reads `tools/sleepmode/.state/state.json` and `tools/brief/.state/away.json` (`ipc.sleep_state_file`, `ipc.away_state_file`); a missing or unreadable file counts as awake and here. Each drop is logged, and the sender is told, e.g. "dropped: the owner is asleep". The one exception is an `urgent` note sent over IPC with `"ring_through": true` (for example a Duo heads-up): it is spoken anyway, and the log says it rang through. A non-urgent note asking to ring through is refused. You may still not answer, so senders plan for that.

Away from the PC, pair the glasses with your phone and run `uv run audiohub run --phone` instead. The phone page then becomes the mic and speaker, over Tailscale. Setup and limits are in [PHONE.md](PHONE.md).

## Commands

All commands accept `--config PATH`, `--input-device DEVICE` and `--output-device DEVICE`. A device is a name substring or an index from `audiohub devices`. Details and exit codes are in `src/audiohub/cli/README.md`.

| Command | Does |
|---|---|
| `devices [--all]` | Lists sound devices and what the configured ones resolve to. `--all` adds DirectSound and WDM-KS. |
| `say TEXT [--voice V]` | Speaks text straight through TTS (with ducking), bypassing the kernel. |
| `voices` | Speaks a sample in each British male voice, announcing its name. |
| `listen [--input-wav FILE]` | Live transcription test: prints each utterance and its STT latency. |
| `run [--no-listen] [--input-wav FILE] [--phone]` | The hub. `--no-listen` is speak-only: kernel, notifications and voice output, no mic or Claude session. `--input-wav` feeds a WAV file in instead of the mic. `--phone` hears and speaks through the phone page ([PHONE.md](PHONE.md)). |
| `phone-link` | Prints the token links for the phone page of a running `run --phone`. |
| `notify TEXT [--source S] [--priority P]` | Sends a message to the running hub to be spoken. Priority is `urgent`, `high`, `normal` (default) or `low`. Exits 1 if it wasn't delivered, including when the hub drops it because you're asleep or away. |
| `mcp` | Runs the stdio MCP server (`notify` and `music_*` tools). Claude Code starts it from the repo's `.mcp.json`. |
| `music ACTION` | `login`, `status`, `play`, `pause`, `toggle`, `next`, `prev`, `volume N`, `play-search QUERY [--kind track\|album\|playlist\|artist]`, `queue QUERY`. |

## Spotify setup

Play, pause, skip and now-playing work without any of this, through the Windows media session (SMTC), for any app in the Windows media flyout. Search, queue and volume need the Spotify Web API:

1. Spotify Premium is required, on the account that owns the developer app.
2. Create a Web API app at https://developer.spotify.com/dashboard.
3. Register the redirect URI `http://127.0.0.1:8888/callback` exactly. Spotify rejects `localhost`.
4. Put the app's client ID in the repo-root `.env` as `SPOTIPY_CLIENT_ID=...` (the `.mcp.json` servers load it), or set it as a user environment variable. No client secret is needed.
5. Run `uv run --env-file ../../.env audiohub music login` once from `tools/audiohub` (from the repo root: `uv run --env-file .env --project tools/audiohub audiohub music login`). Drop `--env-file` if you used a user environment variable. The token is cached in `.cache/` and refreshes itself.

`uv run --env-file ../../.env audiohub music status` shows the backend, the login state and what's playing.

## Known limits

- **Headset quality while listening.** The mic stays open for the whole of `run` (and `listen`), and an open mic switches the glasses to the mono Hands-Free profile, so music and Claude's voice sound like a phone call. `say`, `voices` and `run --no-listen` don't open the mic.
- **Barge-in relies on text, not echo cancellation.** With `audio.barge_in` on (the default) the mic stays live while Claude speaks, so the glasses mic can hear Claude. While Claude is still playing, and until you could have heard it stop, a transcript is dropped when it mostly repeats the sentences Claude said in the last `audio.echo_tail_s` (2 s, the Bluetooth lag) plus a second, and anything without "stop" or a wake phrase is ignored. Once you have heard Claude stop (`audio.reply_after_s`, 1.3 s after its audio ends, 1.8 s in phone mode), what you say is a reply. Until the echo tail ends it is dropped only if it reads as Claude's last words in order: exactly, when it has fewer than two content words ("do it?" right after "...should I do it?"), else with up to one content word in four misheard, missed or extra, though never a leading "yes" or "no" Claude didn't say there. For 4 s after the tail it is dropped only if it is word for word Claude's last words (case and punctuation aside) and 3+ words long. So quick answers such as "yes", "go ahead" or "yeah, do that one" get through, and after the tail so does "Please delete the old logs." after "...delete the old logs?". A stop, a wake phrase or a yes/no answer also gets the looser checks, since a false one costs more than saying it again. Each dropped echo is logged with what it matched and when. The costs: a real "stop" is ignored while Claude's own recent sentence contains "stop" or "stopped", and a bare "Claude" while it says "Claude" or "cloud" (say it again a moment later, or say "Hey Claude"); a reply that is exactly Claude's last words ("do that one" after "...should I do that one?") is taken for its echo, and in the echo tail (from 1.3 s to 2 s after the audio ends) so is a one- or two-word one ("send it" after "Shall I send it?"), one that only adds common words such as "just", "and" or "now" to two or more of Claude's last content words ("Just play some jazz." after "Would you like me to play some jazz?"), or one with a word added to four or more content words ("Please delete the old logs."); an answer with a yes-word Claude's question said itself ("Fine." after "...check everything is fine?") is taken for its echo until 4 s after the tail, so answer with another one; and if the mic hears Claude loudly, the voice detector can merge Claude's echo and your words into one long utterance that only ends when Claude stops. Then the interruption is lost and only the echo check runs. Set `barge_in = false` for the old half-duplex loop: the mic is muted while Claude speaks and for `echo_tail_s` after, and for 4 s after that a transcript of 3+ words mostly from Claude's last few, in any order, is dropped. Two things differ from the old loop on purpose: no follow-up window after a batch "stop" cut short, and "stop" closing the window.
- **Follow-ups.** The no-wake-phrase follow-up window opens once you have heard Claude's audio end (not after a barge-in or a stop) and closes as soon as a request is accepted, or after "stop".
- **Kernel fast path.** A lone reply of up to 80 words (`kernel.max_spoken_words`) that isn't code-heavy, or a lone urgent message, skips Sonnet and is spoken at once, verbatim. Anything longer, code-heavy, or arriving with other messages pending waits 3-8 s for the Sonnet dispatcher, which may condense it.

## Architecture

`run` opens the glasses mic once. `stt` segments speech with Silero VAD and transcribes it with Whisper, and `loop` routes each transcript: wake phrase, follow-up or stop. Requests go to `brain`, one persistent Claude Code session (claude-agent-sdk) rooted at the repo, which runs quick tools itself and hands every bigger job to the main Signal session. Every reply, question and notification then passes through `kernel`, where a Sonnet dispatcher orders it, holds it or condenses it, with fixed rules so nothing is lost. `loop` speaks the result with `tts` (Kokoro), and `audio` plays it and ducks Spotify meanwhile. Other agents reach the same kernel through a loopback notification server (`audiohub notify`, or the `mcp` server's `notify` tool). `music` controls Spotify or SMTC for the CLI and MCP tools, and `loop` uses it to pause the music while you talk with Claude (`music.pause_on_wake`). `phone` lets a phone page stand in for the mic and speaker (`run --phone`), `config` holds settings for all of them, and `cli` is the command line.

## Glasses notes

Under WASAPI the glasses show up as `Headset (BT-Glasses-01)` (the 16 kHz mic) and `Headphones (BT-Glasses-01)` (the output), so `"BT-Glasses"` matches both. They have a single output endpoint, and audiohub's WASAPI streams convert rates automatically, so the same output works with the mic open or closed. Devices are looked up again each time a stream opens, so a reconnect, which renumbers them, doesn't break the config. If the glasses are paired but not connected, only WDM-KS lists them, and `devices` prints a hint saying so.

## Development

```
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
```

Tests mirror `src/audiohub/` under `tests/`. Hardware, models and the Claude SDK are tested by hand through the CLI commands.
