# browser_tool.backends

Where Edge runs. A backend opens the Playwright `BrowserContext` that every safety control in the tool works on (routing, redaction, gates, the Duo watch), so those controls are the same for each backend. The design is `refdocs/research/docker-browser.md`.

## Public API (`from browser_tool.backends import ...`)

- `Backend` (Protocol), used by `browser_tool.session.BrowserSession`:
  - `open_context(playwright, policy)` starts the browser and returns its context, hardened before any page action.
  - `close()` ends the browser the backend started. It never blocks, and a second call does nothing.
  - `is_job_stale()` runs before every tool call; True means end the browser now.
  - `job_label` prefixes owner dialogs and Duo voice notes (`"docker job 1a2b3c"`, or None).
  - `idle_close_s` is the quiet spell after which the server closes the browser, or None.
  - `guest_block` is a `policy.GuestBlock` for the policy, or None.
  - `downloads_incoming` is where the browser writes in-flight downloads, or None when it refuses them (docker jobs always do).
- `BackendError`: the browser can't start. Its message is ours and is shown to the model.
- `LocalBackend(settings)`: the default. The persistent desktop profile, launched with `build_launch_options` (Chromium sandbox on, service workers blocked, never HAR, video or tracing, `--no-proxy-server` unless `use_system_proxy`). With `[downloads] enabled` (the default) it accepts downloads into `downloads_incoming`, a folder inside the profile that is cleared before each launch, and `browser_tool.downloads` moves them out; otherwise `downloads_incoming` is None and downloads are refused. `disable_password_saving(profile_dir)` merges `DISABLED_SAVING_PREFS` into the profile first (verified via `edge://prefs-internals`). No job label, no idle close, no guest block.
- `DockerBackend(settings, addresses=None)`: one throwaway container per job (`browser-tool --backend docker`).
  - A job starts on the first tool call that needs the browser. Before it: `docker info` ("Docker Desktop isn't running. Start it and try again."), the image `IMAGE` (`signal-browser:latest`) must exist, and its Edge must not be a major version behind the repo's latest stable (`compare_versions`; an older build only warns). The refusal names `REBUILD_COMMAND`.
  - Each job gets a 6-hex-digit id (container `signal-browser-<id>`, label `signal.browser.job=<id>`) and its own relay token, kept in memory.
  - The container runs the design's run line (`run_arguments`): published on `127.0.0.1` only, no mounts, `--cap-drop=ALL` plus `NET_ADMIN`, `SETUID`, `SETGID` and `SETPCAP`, `no-new-privileges`, the repo's `seccomp.json` by absolute path, IPv6 off. The token and the block list reach it through docker's own environment (`-e NAME`), never a command line.
  - The host polls the relay with an authenticated `GET /json/version` for up to 30 s ("the browser container didn't start"), then connects over CDP with the token in `headers`, sends `Browser.setDownloadBehavior deny` and repeats Playwright's service-worker blocker before returning the context.
  - A job ends when the server exits, after `[browser] idle_close_min` without a tool call, when the host gets a new IPv4 address, or when its browser goes away. Ending it starts `docker rm -f`. If the server is killed, the relay's own idle exit removes the container within about a minute.
  - Its guest block (Layer 1) refuses `docker.internal`, `localhost`, non-global IP literals and the host's addresses. The guest's iptables (Layer 2) rejects `BLOCKED_GUEST_CIDRS` plus each host address as a `/32` (`block_cidrs`).
- `HostAddresses`: every IPv4 address the host has had since the server started (`getaddrinfo(gethostname())`), refreshed on each tool call.
- `JobSpec`, `run_arguments`, `run_docker`: the docker CLI pieces, also used by the `docker`-marked test.

## Files

- `types.py`: `Backend` and `BackendError`.
- `local.py`: `LocalBackend`, the launch options and the persistent launch.
- `profile_prefs.py`: the Preferences merge for the desktop profile.
- `docker_backend.py`: `DockerBackend`, the job lifecycle.
- `docker_box.py`: the docker CLI calls, all with `CREATE_NO_WINDOW`: `docker info`, the run line, the port read-back, the readiness poll and `docker rm -f`.
- `remote_cdp.py`: `connect_over_cdp` and the hardening before any page action.
- `edge_version.py`: the image's Edge against `Packages.gz` (cached for a day; per image id for the image).
- `host_addresses.py`: the host's addresses and the job's block list.

## Dependencies

`playwright`, `browser_tool.config`, `browser_tool.policy` and `browser_tool.downloads` (the incoming folder's name and cleanup). The docker backend calls the `docker` CLI (Docker Desktop) and needs the image built from `tools/browser/docker/`. No new Python dependency.
