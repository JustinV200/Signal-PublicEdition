# Docker browser: design

How `browser-tool --backend docker` runs each browser job in a throwaway Linux container while every safety control stays on the host. **[tested]** marks something checked in the phase 0 spike (`tools/browser/docker/probes/spike.py`). This doc extends `tools/browser` (see its README), which follows `browser-control.md` and the vault contract in `password-vault.md`.


## 1. Safety code stays on the host, only Edge goes in the guest

```
Claude --stdio MCP--> browser-tool --backend docker (host)          container (one per job)
                      policy, redaction, gates, Duo watch,  --CDP-->  relay (token) -> Edge CDP on 127.0.0.1
                      owner dialogs labelled "docker job <id>"        Xvfb, iptables, Edge policies
```

- Every control in `tools/browser` works on a Playwright `BrowserContext` or `Page`. Only `session/launcher.py: launch_context` knows how the context is made, so that function is the seam.
- Running all of `tools/browser` inside the guest is rejected: the vault and the owner dialogs are bound to the host.
- `connect()` (the Playwright protocol) only makes fresh contexts, and the later login phase needs a real profile in the guest. So the host uses `connect_over_cdp`. The phase 0 spike showed every control works over it, with two changes: the selector engine is registered after connecting, and the CDP download deny is the control that matters.

## 2. The seam and the docker server

- **Picking the backend and its config.** `browser-tool --backend docker --config tools/browser/browser-docker.toml` is registered as a second MCP server, `browser-docker`, beside the unchanged `browser`. The model uses `mcp__browser-docker__*` when the owner asks for a container job.
  - The backend comes from the flag, not from a TOML section, because `config/loader.py` rejects unknown sections with `ConfigError`.
  - `browser-docker.toml` is a copy of the same schema, gitignored like `browser.toml`; add it to `.gitignore` in phase 1.
  - `allow_all` lives only in `browser-docker.toml`, so the desktop browser's `browser.toml` keeps its allowlist.
- **No vault in docker jobs.** The two credential tools would otherwise come along, because `server/main.py` passes `LazyVaultFiller()` and the server instructions in `server/app.py` tell the model to use `fill_login`. So with `--backend docker`:
  - `main.py` passes `MissingVaultFiller("vault fills are off in docker jobs")` (`credentials/missing_vault.py`), so the vault is never imported.
  - `list_credentials` and `fill_login` aren't registered.
  - The server gets its own instructions: no `fill_login` sentence. It adds: "This browser runs in a throwaway container: nothing persists between jobs and there are no saved logins. Never type passwords or codes."
  - Other model-facing text also says to use `fill_login`: the `type_text` description (`server/tool_definitions.py:42`) and the password-field refusal (`actions/interaction.py:49`). The docker server gets its own versions of both.
- **`browser_tool/backends/`.** Each backend exposes `open_context(playwright)` and `close()`.
  - `local.py`: today's `launch_persistent_context` code, moved.
  - `remote_cdp.py` connects with `connect_over_cdp(endpoint, headers={"Authorization": "Bearer <token>"})` (https://playwright.dev/python/docs/api/class-browsertype), takes `browser.contexts[0]`, and then, before anything touches a page:
    - sends `Browser.setDownloadBehavior {behavior: "deny"}` through `browser.new_browser_cdp_session()`. A CDP-connected default context gets the driver's defaults, `acceptDownloads: "accept"` and `serviceWorkers: "allow"` (`defaultNewContextParamValues` in the 1.64.0 driver's `coreBundle.js`).
      - This deny is the download control that matters **[tested]**. While a CDP client has set `allow` or `allowAndName`, Edge ignores `DownloadRestrictions`, and the connect itself sets `allowAndName` (`CRBrowserContext.initialize`). The policy only holds under `default`.
    - repeats Playwright's own service-worker blocker with `add_init_script` (`ServiceWorkerContainer.prototype.register = async () => {...}`, same file).
  - **The selector engine is registered after connecting.** The Python client sends selector engines only in a new context's creation params, or later to contexts it already tracks (`_selectors.py`, `_browser.py`). A CDP default context isn't created by the client, so an engine registered before `connect_over_cdp` is an "Unknown engine" there **[tested]**.
    - `BrowserSession._open_context` registers before `launch_context` today. Phase 1 moves `register_sensitive_engine` to just after `backend.open_context`, which works for both backends.
  - `docker_box.py` drives the `docker` CLI through `subprocess`. No new Python dependency.
    - Every call passes `creationflags=subprocess.CREATE_NO_WINDOW` (read with `getattr`, so the module imports off Windows). `docker.exe` is a console program, and the MCP server has no console, so otherwise each call would flash a window.
    - The prototype is `tools/browser/docker/probes/docker_job.py`.
- **Close hook.** `BrowserSession.close()` calls `context.close()`, then `backend.close()`, which runs `docker rm -f` for docker. The context's `close` event, fired when the connection drops, also calls `backend.close()`.
  - That handler is synchronous, so `backend.close()` never blocks: it starts `docker rm -f` without waiting.
  - It is idempotent: a second call does nothing.
- **What a job is.** A job is one container. It starts on the first browser tool call of a `browser-docker` server process, and it ends when:
  - the server exits;
  - no tool call has arrived for `idle_close_min` minutes (default 15, a new `[browser]` key that only the docker backend reads);
  - or the host gets a new IPv4 address (section 5).

  The next tool call starts a fresh job, with a new container and a new id.
- **Lazy start.** `docker info` runs on the first tool call that needs the browser, not at server start, so registering `browser-docker` doesn't touch Docker. On failure the tool returns "Docker Desktop isn't running. Start it and try again."
- **Job ids.** Each job gets a short id, used in the container name and label. Owner dialogs and Duo voice notes are prefixed "docker job <id>". The `local` backend adds no prefix.

## 3. The guest image and process tree

- **Base image.** `tools/browser/docker/` holds the Dockerfile; the phase 0 prototype is there now (its README). The base is `debian:trixie-slim`, pinned by digest, and the build runs `apt-get upgrade`, so Debian's security fixes released since the digest come in. Bump the digest by hand now and then so the upgrade stays small.
  - `microsoft-edge-stable` comes from Microsoft's apt repo (`https://packages.microsoft.com/repos/edge stable main`).
    - Its key is committed as `tools/browser/docker/microsoft.asc`, and the build checks it against the pinned fingerprint `BC52 8686 B50D 79E3 39D3 721C EB3E 94AD BE12 29CF`.
    - apt trusts the key for that repo only (`signed-by=`).
    - The repo's `InRelease` is signed by that key (`EB3E94ADBE1229CF`, checked 2026-10-19).
    - Microsoft also publishes `microsoft-2025.asc` (`AA86 F75E 427A 19DD 3334 6403 EE4D 7792 F748 182B`).
    - If the repo switches to that key, the pinned check fails the build, as intended, and the pin is updated by hand.
  - Edge's postinst rewrites our source into its own deb822 `microsoft-edge.sources` (pointing at `repos/edge-stable`, with a keyring it installs, which is the same key) and adds a `cron.daily` job that keeps it **[tested]**. The image never runs apt again, so the build deletes all three.
  - Also installed: `ca-certificates` (the repo is HTTPS), `xvfb`, `python3` (3.13.5), `iptables` and `iproute2` (`ip`, `ss`). `setpriv` comes from `util-linux`, which the base already has. `gpg` is installed for the fingerprint check, then purged.
  - The policy folder is made with `install -d -m 0755` before the `COPY`, because `COPY --chmod=0644` gives the folders it creates the file's mode. Edge then can't enter them, and the policies silently don't load **[tested]**.
- **Headed under Xvfb from phase 1.** That matches the headed `local` backend, and it's the same image the phase 2 viewer needs. Xvfb runs as `Xvfb :99 -nolisten tcp -screen 0 1920x1080x24`, so pages lay out at a desktop size.
  - Xvfb also listens on the abstract unix socket `@/tmp/.X11-unix/X99`. File permissions don't guard it; anything in the container's network namespace can connect. Pages can't open unix sockets, so this is only a phase 2 note.
- **Process tree:**
  ```
  docker-init (PID 1, from --init; the only process left as root)
  └─ entrypoint.sh  (root, set -eu): apply the firewall, verify it, exec setpriv ... python3 main.py
     └─ main.py     (user "edge", no capabilities): pops SIGNAL_* from its env, starts the
        │            children, then serves the relay (relay.py)
        ├─ Xvfb :99 -nolisten tcp -screen 0 1920x1080x24
        └─ microsoft-edge <switches> --host-resolver-rules=<rules> about:blank
  ```
  - `setpriv --reuid=edge --regid=edge --init-groups --inh-caps=-all --bounding-set=-all`.
  - Edge's CDP flags are `--remote-debugging-port=9222` plus a non-default `--user-data-dir=/home/edge/profile` (Chromium 136+ ignores the port with the default dir), and `--no-proxy-server`.
  - Xvfb and Edge get an explicit environment: `DISPLAY=:99`, `HOME=/home/edge` and `PATH=/usr/local/bin:/usr/bin:/bin`, with no `SIGNAL_*`. `microsoft-edge` is a shell script, so it needs a `PATH`. It adds its own `CHROME_WRAPPER`, `CHROME_VERSION_EXTRA`, `GNOME_DISABLE_CRASH_DIALOG`, `PWD` and `SHLVL`, and starts two `cat` processes for its output **[tested]**.
  - The relay opens its port only after `127.0.0.1:9222/json/version` answers.
  - The host polls with an **authenticated** `GET /json/version` until it gets 200, for up to 30 s, then returns "the browser container didn't start" instead of hanging. A bare TCP connect isn't readiness: Docker Desktop's port proxy accepts a connection on the published port with nothing listening in the container, then closes it **[tested]**. In the spike, 200 came about 1 s after `docker run`.
  - `os.environ.pop` doesn't erase `/proc/<relay>/environ`, and a process running as `edge` is dumpable. So the relay first calls `prctl(PR_SET_DUMPABLE, 0)` through `ctypes`. The call is guarded by `sys.platform.startswith("linux")`, so host-side tests can import the module.
    - Verified: `docker exec -u edge … cat /proc/<relay>/environ` fails. So does the same as container root, which lacks `CAP_SYS_PTRACE` **[tested]**. The token is still visible to `docker inspect`, the same-user limit. See the threat table.
  - The relay is stdlib-only, and runs on Debian's `python3` (3.13.5) with `-E -s`. Its folder `/opt/signal` is root-owned, so `edge` can't plant modules beside it.
  - The Dockerfile creates `/run/signal`, owned by `edge`, and `/tmp/.X11-unix` (root, 1777), so Xvfb doesn't complain. Root in the entrypoint has no `CHOWN`, `DAC_OVERRIDE` or `FOWNER`, so anything that touches `edge`'s files runs in the relay, as `edge`.
  - In the container's user namespace, only `docker-init` holds capabilities (`NET_ADMIN`, `SETUID`, `SETGID`, `SETPCAP`). Every other process is `edge` with `NoNewPrivs` and seccomp mode 2.
    - Chromium's sandbox zygote shows `CapEff` with `CAP_SYS_ADMIN`, but in the user namespace the sandbox made for itself, which the renderers share **[tested]**.
    - A phase 1 "no capabilities" assertion has to compare user namespaces (`/proc/<pid>/ns/user`) the way `probes/check_guest.py` does.
- **The run line**, as the backend builds it:
  ```
  docker run -d --rm --init --name signal-browser-<id> --label signal.browser.job=<id> \
    --cap-drop=ALL --cap-add=NET_ADMIN --cap-add=SETUID --cap-add=SETGID --cap-add=SETPCAP \
    --security-opt no-new-privileges --security-opt seccomp=<repo>\tools\browser\docker\seccomp.json \
    --sysctl net.ipv6.conf.all.disable_ipv6=1 -p 127.0.0.1::9333 \
    -e SIGNAL_RELAY_TOKEN -e SIGNAL_BLOCK_CIDRS -e SIGNAL_RESOLVER_RULES  signal-browser:latest
  ```
  - `-e NAME` with no value copies the variable from the `docker` process's own environment, so the token never shows in a command line.
  - `docker port` reads back the random host port.
  - The seccomp path is absolute (the backend resolves it with `resolve_tool_path`), because the `docker` CLI reads it relative to its own working directory.
  - The spike ran exactly this line, with the image tagged `signal-browser-spike:phase0`. `docker inspect` showed the port bound to `127.0.0.1` only, no mounts, not privileged, and only the four added caps **[tested]**.
- **Seccomp.** `seccomp.json` is Docker 29.8.2's own default profile plus one unconditional rule that allows `clone`, `unshare`, `setns` and `chroot`.
  - Since engine 29 the default profile lives outside the moby tree, in `moby/profiles` at `seccomp/default.json`. `moby/moby` tag `docker-v29.8.2` vendors `seccomp/v0.2.3`.
  - `tools/browser/docker/make_seccomp.py` appends the rule and changes nothing else.
  - Chromium's namespace sandbox needs all four. The default profile gates them on capabilities (`CAP_SYS_ADMIN`, and `CAP_SYS_CHROOT` for `chroot`), and those gates are resolved when the container is created, so under `--cap-drop=ALL` all four are filtered.
  - Chromium calls `chroot("/proc/self/fdinfo/")` in `Credentials::DropFileSystemAccess`, so without the rule Edge won't start.
    - Verified: under Docker's built-in default, Edge logs "Failed to move to new namespace ... Operation not permitted". The setuid fallback refuses to run (not root, `no_new_privs`), the zygote exits, Edge dies with SIGTRAP, and the relay never listens **[tested]**.
    - With the rule, `edge://sandbox` shows the namespace sandbox, PID and network namespaces, and seccomp-BPF with TSYNC: "You are adequately sandboxed." Edge's stderr has no EPERM or SIGSYS; it's only D-Bus noise.
  - Playwright's `utils/docker/seccomp_profile.json` (https://github.com/microsoft/playwright/blob/main/utils/docker/seccomp_profile.json) was the earlier plan. It gates `chroot` the same way, and it lacks `clone3`, `faccessat2`, `close_range`, `openat2` and `epoll_pwait2`.
  - A missing sandbox fails closed: Edge refuses to start rather than running unsandboxed, since we never pass `--no-sandbox` (https://playwright.dev/python/docs/docker).
- **Edge flags.**
  - They are Playwright's curated `chromiumSwitches` (in `coreBundle.js`), minus four that turn off protections an `allow_all` guest wants: `--disable-background-networking`, `--disable-component-update`, `--disable-client-side-phishing-detection` and `--disable-popup-blocking`.
  - `HttpsUpgrades` is also taken out of the `--disable-features` list, so HTTPS upgrades stay on.
  - `--disable-dev-shm-usage` stays in, so no `--shm-size` is needed.
  - Never `--no-sandbox`, and never `--remote-allow-origins`.
  - The relay passes `SIGNAL_RESOLVER_RULES` to Edge as one argv element, `--host-resolver-rules=<value>`, through a list `subprocess` call with no shell.
- **Edge managed policies** go in `/etc/opt/edge/policies/managed/` (`signal.json`). The path is verified: `edge://policy` lists all nine with no errors **[tested]**. The folder is root-owned and not writable by `edge`.
  - Edge watches the folder: when the spike deleted the file, `edge://policy` dropped the policies within the 30 s the probe waits.
  - Password manager and autofill: `PasswordManagerEnabled`, `AutofillAddressEnabled` and `AutofillCreditCardEnabled` are false.
  - Downloads: `DownloadRestrictions=3`.
  - Sync, sign-in and extensions: `SyncDisabled=true`, `BrowserSignin=0`, `ExtensionInstallBlocklist=["*"]`.
  - Startup: `HideFirstRunExperience=true`, `NewTabPageLocation="about:blank"`.
- **Patching.** The image freezes Edge at build time.
  - The backend reads the image's Edge version once per image id (`docker run --rm --network none --entrypoint microsoft-edge <image> --version`).
  - It compares that with the latest `microsoft-edge-stable` in the repo's `Packages.gz`, fetched with stdlib `urllib` and cached for a day.
  - It doesn't compare with the host's Edge, which can be the stale side.
  - It **refuses** when the major version is behind, and prints the rebuild command (`docker build --pull --no-cache -t signal-browser:latest tools/browser/docker`).
  - It **warns** when only the build number is behind.
- **Service workers.** Once profiles persist (phase 4), the relay, running as `edge`, deletes `<profile>/Default/Service Worker/` before it starts Edge, because workers already registered would bypass `context.route`.

## 4. Auth and the relay (codingrules section 7)

- Edge's CDP port stays on the container's own `127.0.0.1:9222`.
- **The relay is the only TCP listener.** The host makes the token per job (`secrets.token_urlsafe(32)`) and keeps it in memory.
- **Every TCP connection is checked.** The `/json/version` fetch and the CDP WebSocket are separate connections.
  - The relay reads the first request head (at most 16 KiB) with a 5 s read timeout. It accepts only `GET <path> HTTP/1.1` with exactly one `Authorization: Bearer <token>` header, compared with `hmac.compare_digest`. It strips that header before forwarding.
  - It answers 401 and closes on the first malformed or unauthenticated request.
    - The spike tried no token, a wrong token, `Basic`, two `Authorization` headers, `POST` with the token, a WebSocket upgrade without it, binary garbage and an oversized head. Each got a 401 at once. A client that sends nothing got its 401 after 5.0 s **[tested]**.
- **`Host` is forwarded unchanged.** Chromium accepts only an IP literal or localhost (`RequestIsSafeToServe`) and builds `webSocketDebuggerUrl` from that Host header (`OnJsonRequest`), both in `content/browser/devtools/devtools_http_handler.cc`.
  - The host connects by IP, so the URL points back at the published port (`ws://127.0.0.1:<port>/devtools/browser/<id>`) **[tested]**.
  - Playwright sends `headers` on every connection: `GET /json/version`, `GET /json/version/` and the WebSocket all reached the relay with the token **[tested]**. So no `ws://` workaround is needed.
- **The relay ends the container when it's no longer used.** It counts only authenticated connections, and exits (stopping and removing the container) when:
  - none arrives within 60 s of start, or
  - the count has been zero for 60 s.

  If the host process dies, its sockets close, so no sweep of stale containers is needed.
  - Measured: after a connected host process was killed (as `taskkill /F` would), the container was gone 61 s later. Unauthenticated connections every 10 s didn't keep it alive **[tested]**.
  - So the phase 1 acceptance is "gone within 75 s", not 60 s.
  - If Edge crashes (the spike sent it `kill -9`), the host's context `close` event fires and the close hook's `docker rm -f` removes the container **[tested]**. The relay also checks its children every second and exits when one dies.
- **Deviations from codingrules section 7**, stated in code comments too:
  - The relay binds `0.0.0.0` inside the container, because Docker's port forwarding arrives on the container's interface.
  - Other containers on the bridge can reach it, so the token is what protects it.
  - The host side is loopback-only.
  - The token is in the container's env, which `docker inspect` shows: the same-user limit from `password-vault.md`.

## 5. The host and LAN block (phase 1)

- **The problem.**
  - With `allow_all`, the likely mode for public-web jobs, `HostPolicy.check_host` allows every host not on the denylist (`policy/host_policy.py`). That includes `host.docker.internal`, private IPs and the host's public address.
  - So an ordinary hostile page, with no exploit, could reach local services on the host and the LAN.
  - DNS rebinding beats name denies, and most of those services are third-party, so tokens can't be required of them.
- **One list.** A single Python constant, `BLOCKED_GUEST_CIDRS`, holds 10/8, 172.16/12, 192.168/16, 169.254/16, 100.64/10 and 127/8. At each job start, the backend appends the host's current IPv4 addresses as `/32`s, from `socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)`, and passes the result as `SIGNAL_BLOCK_CIDRS`. Both layers use it.
  - The backend recomputes the host addresses on every tool call.
  - If a new one appears (a new DHCP lease, another network), it ends the job. The next call starts a fresh job with the new list.
- **Layer 1, the policy**, applied by the docker backend whatever `allow_all` says:
  - Routing and `--host-resolver-rules` deny `docker.internal`, `*.docker.internal`, `localhost`, `*.localhost` and the host IPs as literals.
  - Routing also rejects any IP-literal host where `not ip.is_global`, after unwrapping `ipv4_mapped`. That catches CGNAT, which `is_private` misses **[tested]**.
- **Layer 2, iptables: the real boundary.** The entrypoint runs under `set -eu`:
  1. Validate every `SIGNAL_BLOCK_CIDRS` entry as an IPv4 CIDR, and refuse an empty list.
  2. In `OUTPUT`, accept `-o lo`, then `ESTABLISHED,RELATED`, then UDP and TCP 53 to the `resolv.conf` nameserver.
     - On the default bridge that's Docker Desktop's `192.168.65.7`, inside 192.168/16. That's why these accepts come before the rejects.
  3. Then REJECT **all** packets to every `SIGNAL_BLOCK_CIDRS` entry.
     - REJECT exists. The image's `iptables` is 1.8.11 on the nf_tables backend, on the WSL kernel 6.18, and needs no `NET_RAW` **[tested]**. So there's no DROP fallback.
     - A blocked connect fails at once with "connection refused" (`ERR_CONNECTION_REFUSED` in Edge).
  4. Set `ip6tables -P OUTPUT DROP` as a backstop to the sysctl.
  5. Never flush the `nat` table, where Docker's DNS rules live.
  6. Before `setpriv`, check each rule with `iptables -C` and the rule count with `iptables -S OUTPUT`, and check that `ip6tables -S OUTPUT` shows `-P OUTPUT DROP`. Exit non-zero unless all match. If the firewall isn't in place, the container dies instead of running open.
     - Verified: an empty list, a list with a hostname, and a CIDR with host bits set (`10.0.0.1/8`) each ended the container before the relay started **[tested]**.
  7. Inbound connections from the host to the relay still work, because their replies are ESTABLISHED.
- **Fallback.** If the block shows trouble, refuse `allow_all` on docker until phase 3 (Q4). The spike showed none.

## 6. The viewer (phase 2)

- **No TCP inside the guest.** A page can reach anything on the guest's loopback (`-o lo` is accepted), and websockify has no origin check. So:
  - x11vnc runs with `-rfbport 0 -unixsock /run/signal/vnc.sock`.
  - websockify uses `--unix-listen=/run/signal/ws.sock --unix-target=/run/signal/vnc.sock`.
  - The relay reaches websockify through `ws.sock` after its cookie check.
  - Pages can't open unix sockets. A compromised browser could, but it would only gain its own screen.
- **The cookie** follows `tools/whiteboard/src/whiteboard/display/server/page_guard.py`:
  - The token arrives once in `?token=`, becomes an HttpOnly, SameSite=Strict cookie that holds an HMAC of the token, and the page redirects to the plain path.
  - The cookie is named `signal_view_<id>`, because cookies are per host, not per port, and every job is on `127.0.0.1`.
  - The relay strips `Cookie` before forwarding anything into the guest.
  - SameSite=Strict doesn't separate ports on `127.0.0.1`, because they're all the same site. So the relay also requires the WebSocket upgrade's `Origin` to equal the viewer's own origin (`http://127.0.0.1:<port>`).
- **`browser-box view <job>`** reads the port and token from the gitignored state file `tools/browser/.state/jobs/<id>.json`. `tools/browser/.state/` must be added to `.gitignore` in phase 2, when the file first appears.
- **The viewer takes input.** The owner can click and type, for a CAPTCHA or a Duo page, and that input is ungated by design. It isn't for logins before phase 4.
