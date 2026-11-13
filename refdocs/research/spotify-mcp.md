# Spotify control for Claude Code / audiohub: research

Researched 2026-10-19. Items marked UNVERIFIED could not be confirmed from primary sources.

## 1. Existing Spotify MCP servers

| | varunneal/spotify-mcp | marcelmarais/spotify-mcp-server |
|---|---|---|
| Repo | https://github.com/varunneal/spotify-mcp | https://github.com/marcelmarais/spotify-mcp-server |
| Runtime | Python, `uvx`/uv, built on spotipy 2.24.0 | Node.js + TypeScript (README demands a very recent Node "Current", min v26.8.1; UNVERIFIED, looks odd) |
| Features | start/pause/skip, search, track/album/artist/playlist info, queue, playlist create/update | ~25 tools: search, now playing, queue, devices, play/pause/skip, volume, playlists, albums, saved tracks, recently played |
| Maintenance | README: "[Notice March 2026]: Inactive project. Most PRs will not be merged." (a search snippet said Feb 2026; either way, abandoned). 48 commits | Third-party listing says last push 2026-03-07 (https://gittrend.io/repo/marcelmarais/spotify-mcp-server, not primary). 70 commits. Release dates not shown on repo page |
| License | MIT | MIT |
| Auth | Spotify OAuth via spotipy. `SPOTIFY_CLIENT_ID/SECRET/REDIRECT_URI` in MCP config env. Redirect must be `http://127.0.0.1:PORT/callback`. README says uvx opens the redirect URI on every tool call; a local clone avoids this | Default stdio: `npm run auth` OAuth flow. Optional HTTP mode with `MCP_AUTH=spotify` (bearer tokens, nothing on disk) |
| Token storage | Not documented (spotipy default is a `.cache` file in cwd; UNVERIFIED for this repo) | `spotify-config.json` in project root holds client ID, secret, access and refresh tokens in plain text |
| Windows | Fine (Python/uv); README gives a Windows config path | Probably fine, but needs a Node install the machine lacks, and a very new Node |
| Security | Secrets in MCP config env (leak risk if `.mcp.json` committed). Unmaintained dependency chain. Third-party code holding a full-scope token | Plaintext refresh token and secret on disk next to code. Same third-party-code risk. Large tool surface (playlist/library writes) |

Other servers exist (mcp.so, glama.ai list many); I did not vet them.

## 2. Spotify Web API constraints (as of Oct 2026)

- **Premium:** playback-control endpoints "only work for users who have Spotify Premium": https://developer.spotify.com/documentation/web-api/reference/start-a-users-playback . Since Feb 2026 every Development Mode app also requires the **app owner** to hold active Premium, or the app stops working: https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide
- **Dev Mode policy:**
  - New apps from 2026-02-11; existing apps migrated 2026-03-09. Max 5 users per app.
  - Client IDs per developer: 1, raised to 25 in July 2026. Quota is now counted per developer account, not per Client ID. 429 body now has `reason: QUOTA_EXCEEDED`: https://developer.spotify.com/documentation/web-api/references/changes/july-2026
  - `GET /search` max limit cut from 50 to 10, default 5 (paginate with offset).
  - Many endpoints removed (batch GET /tracks etc., browse, artist top-tracks, `GET /users/{id}`). The guide lists **no changes to player/queue endpoints**. `GET /me` no longer returns `product`.
  - Extended Quota is effectively for orgs with 250k+ MAU (secondary source: https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security). Irrelevant for personal use.
- **Create a dev app:** https://developer.spotify.com/dashboard , log in, Create app, choose "Web API", set redirect URI, copy Client ID and Secret. (Click-path from general knowledge, not re-fetched.)
- **Redirect URIs** (https://developer.spotify.com/documentation/web-api/concepts/redirect_uri): HTTPS required, except HTTP is allowed for loopback IP literals `http://127.0.0.1:PORT/...` or `http://[::1]:PORT/...`. `localhost` is NOT allowed. Exact match required; loopback may omit the port at registration.
- **Rate limits:** rolling 30-second window; 429 with `Retry-After` seconds. No numeric dev-mode figure on the page (it defers to a quota-modes page I did not fetch): https://developer.spotify.com/documentation/web-api/concepts/rate-limits . Fine for voice-driven use.
- **Scopes** (https://developer.spotify.com/documentation/web-api/concepts/scopes):
  - `user-modify-playback-state`: play/resume, pause, next, previous, volume, seek, shuffle/repeat, transfer, add to queue
  - `user-read-playback-state`: devices, current playback state
  - `user-read-currently-playing`: currently playing, get queue
  - Search needs no user scope (my understanding; not re-verified).
- **Needs an active device.** The Web API controls Spotify Connect devices, so the desktop app must be open. Not re-verified in this pass.

## 3. Local alternative: Windows SMTC

- API: `GlobalSystemMediaTransportControlsSessionManager` (Windows.Media.Control). Python projection: per-namespace `winrt-*` packages (e.g. `winrt-Windows.Media.Control` plus `winrt-runtime`); cp312 wheels exist (https://pypi.org/project/winrt , https://www.pypi.org/project/winrt-Windows.Devices). Example consumer: https://py-now-playing.readthedocs.io . `winsdk` is the older predecessor; I found nothing on its status (UNVERIFIED), so prefer `winrt-*`.
- Can do: find the Spotify session (source app id contains "Spotify"); read title/artist/album, play state, timeline; play/pause/toggle/next/previous/seek, shuffle/repeat. No Premium, no developer app, no login, no network.
- Cannot do: search, choose a track/playlist/album, read or edit the queue, set Spotify's own volume (use pycaw for session volume), control Spotify on another device, or work when Spotify is closed.
- Multi-package install is slightly fiddly; wrap it in one small module with a clean import-failure fallback.

## 4. Recommendation

**Choose (b): a small `music` package inside audiohub, using spotipy plus an SMTC fallback, exposed through audiohub's own FastMCP server.**

Why:
- Both existing servers are weak fits: varunneal's is flagged inactive; marcelmarais's needs a Node install this machine lacks (and a bleeding-edge Node) and stores secrets in plaintext in the repo dir.
- The needed surface is small (play, pause, next, prev, volume, search, queue, now playing): about 8 thin tools over spotipy, easy to keep within the repo's small-files rule.
- One MCP server for Claude Code instead of two, and the voice assistant can call the same Python functions directly with no MCP hop.
- We control where tokens live and avoid running third-party code with a Spotify token.
- SMTC gives a no-login, no-Premium degraded mode for play/pause/skip/now-playing if the Web API is unavailable.
- Cost: we own maintenance against Spotify policy churn (Feb and July 2026 changes show it is real). Mitigate with a narrow endpoint set; none of the player/search endpoints we need were removed.

Suggested layout: `music/spotify_client.py` (spotipy wrapper, 429 retry), `music/smtc.py` (winrt fallback), `music/controller.py` (picks backend), plus a FastMCP tool module. Use spotipy `SpotifyOAuth` with `cache_path` pointing at a gitignored file.

### What the user must do
1. **Premium: yes**, on the account that owns the developer app (policy since Feb 2026) and for playback control. Without it only the SMTC fallback works.
2. Create a developer app at https://developer.spotify.com/dashboard (Web API).
3. Copy the **Client ID** and **Client Secret**.
4. Register the redirect URI exactly as `http://127.0.0.1:8888/callback` (not `localhost`).
5. If the listening account differs from the owner, add it under the app's User Management (max 5 users).
6. **First run:** a browser opens for Spotify consent for scopes `user-modify-playback-state user-read-playback-state user-read-currently-playing`; the token is cached and refreshes automatically afterward.
7. **Credentials:** env vars `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI` (spotipy's native names) from a gitignored `.env` or user-level Windows env vars. Token cache file gitignored too. Never in a committed `.mcp.json` (AGENTS.md already bans committing `.env`).
8. Keep the Spotify desktop app open and logged in so there is an active device.

### Biggest risks
- Spotify Dev Mode policy churn (5 users, Premium-owner rule, endpoint removals) may break things again.
- A Premium lapse disables Web API control.
- "No active device" errors when Spotify is closed or idle.
- Search capped at 10 results per call.
- SMTC wheel/packaging on Python 3.12 not tested here.
- Not verified: numeric dev-mode rate limits, current dashboard click-path, varunneal token cache location, marcelmarais exact last release.
