# tools/browser/docker

The guest image of `browser-tool --backend docker` (`src/browser_tool/backends/`), plus the host-side probes from the phase 0 spike in `refdocs/research/docker-browser.md`. Build the image once, and again whenever the backend says its Edge is behind:

```
docker build --pull --no-cache -t signal-browser:latest tools/browser/docker
```

## What's here

- `Dockerfile`: Debian trixie-slim (pinned by digest, then `apt-get upgrade`), Edge for Linux from Microsoft's apt repo, Xvfb, python3, iptables, iproute2.
  - `microsoft.asc` is Microsoft's release key, committed here. The build checks its fingerprint (`BC52 8686 B50D 79E3 39D3 721C EB3E 94AD BE12 29CF`), and apt trusts it for the Edge repo only (`signed-by`).
  - Edge's postinst rewrites the apt source into its own `microsoft-edge.sources` plus a cron job. The build deletes those, because the image never runs apt again.
- `seccomp.json`: Docker's default profile plus one rule that allows `clone`, `unshare`, `setns` and `chroot` without capabilities, which Chromium's namespace sandbox needs. Regenerate it with `make_seccomp.py` when the engine updates (see below).
- `guest/`: the files baked into the image.
  - `entrypoint.sh` (root): validates `SIGNAL_BLOCK_CIDRS`, applies and re-checks the iptables rules, then drops to user `edge` with `setpriv` and execs `main.py`.
  - `main.py` (as `edge`): `PR_SET_DUMPABLE` off, pops the `SIGNAL_*` variables, starts Xvfb and Edge, then serves the relay until it's idle for 60 s.
  - `relay.py`: the token-checking TCP relay on port 9333, in front of Edge's CDP port on `127.0.0.1:9222`.
  - `processes.py`, `edge_switches.py`: the Xvfb and Edge command lines, and their explicit environment.
  - `edge_policy.json`: Edge managed policies, installed root-owned in `/etc/opt/edge/policies/managed/`.
- `probes/`: host-side spike scripts. `spike.py` runs every check and prints PASS/FAIL lines; rerun it after a Playwright or Edge upgrade. `docker_job.py` was the prototype of the backend's `docker_box.py`. `guest_*.py` run inside a container, fed on stdin; the `docker`-marked test reuses `guest_connect.py`.

## Run the spike

Docker Desktop must be running and the image built (above). From the repo root:

```
uv run --project tools/browser --frozen --no-sync python tools/browser/docker/probes/spike.py
```

The image takes about 300 MB of downloads and 1.6 GB on disk. The spike takes about 4 minutes and removes every container it starts.

Its no-firewall baseline makes TCP connections, with no data sent, to the host's whiteboard daemon (:8770) and any local service listening on :1234. That shows they are reachable when no firewall is in place.

## Regenerate seccomp.json

Get `seccomp/default.json` from `moby/profiles` at the version the running engine vendors (`vendor/modules.txt` in `moby/moby` at tag `docker-v<engine version>`; engine 29.8.2 vendors `seccomp/v0.2.3`), then run:

```
python make_seccomp.py <downloaded default.json> seccomp.json
```

## Depends on

- Docker Desktop with the WSL 2 backend.
- The probes use the `tools/browser` venv: Playwright 1.64.0 and `browser_tool.redaction`.
- The guest code is stdlib-only (Debian's Python 3.13).
