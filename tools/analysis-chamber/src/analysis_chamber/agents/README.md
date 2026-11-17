# analysis_chamber.agents

Builds the Agent SDK sessions a chamber run uses, and runs them.

## Public API (`from analysis_chamber.agents import ...`)

- `RunContext(run_dir, manifest, config)`: one run as the builders see it.
- `TurnResult(session_id, text, is_error, structured=None, permission_denied=False)`. `is_error` is False only when the `ResultMessage` has subtype `"success"` and `is_error` False. A turn with no `ResultMessage` is an error. `structured` is the CLI's `structured_output` when the options set `output_format`. `permission_denied` is True when the result lists any `permission_denials`.
- `AgentRunner` Protocol: `async run(options, prompt, resume=None) -> TurnResult`. `SdkRunner` is the real one (a `ClaudeSDKClient` per turn). Cancelling the awaiting task disconnects the client and stops the CLI.
- `lead_options(ctx, on_source=None, io=None)`, `plan_options(ctx)`, `critic_options(ctx)`, `qa_options(ctx, resume, fork=False)`. `fork=True` with `resume=None` raises `ValueError`.
- `PASS_THROUGH_TOOLS` (the only non-chamber MCP tools whose output isn't swapped for an extract) and `WITHHELD` (the fail-closed placeholder).

## What every session gets (`options/base.py`)

- `cwd=ctx.run_dir` and `permission_mode="bypassPermissions"`.
- `security.disallowed_tools(role)` and `security.build_hooks(ctx, role)`. The spikes showed both hold under bypass and reach sub-agents (Task/Agent), so the lead may spawn sub-agents. `allowed_tools` restricts nothing under bypass, so it isn't used for isolation.
- `setting_sources=[]`: no CLAUDE.md or AGENTS.md (the repo's orchestrator rules would have the lead delegate and commit), no user hooks, no plugins. The playbook is named in the system prompt, and its folder is in `add_dirs`.
- `strict_mcp_config=True` with explicit servers, plus `ENABLE_CLAUDEAI_MCP_SERVERS=false`. Without these the claude.ai Gmail and Calendar connectors load.
- `env`: `kit.run_env(...)` plus `nested.SESSION_ENV` (`ENABLE_CLAUDEAI_MCP_SERVERS=false`, `SIGNAL_BRIEF_SURFACE=managed`), the env nested sessions get too.

## Roles

- **Lead:** the in-process `chamber` server and the Signal servers in `security.mcp_servers_for("lead")`, loaded from `.mcp.json` (`signal_mcp.py`). The outer `uv run` is rewritten to `uv run --directory <repo_root>` so each server starts from any cwd. The browser server is never in the lead's session; only the signup sub-session gets it. It also gets the PostToolUse free-text swap and the PostToolUseFailure warning.
- **Plan:** `plan_options` is the lead (same model, prompt, hooks and disallowed list) with no MCP servers at all, so plan and revise turns can't collect anything before approval (spec 7.1).
- **Critic:** a fresh session with no MCP servers. It may run code but is told not to change the lead's files.
- **Q&A:** no MCP servers. It resumes `resume` if given, and `fork=True` adds `fork_session` so a mid-run lead session is left untouched.

## The `chamber` server (`chamber_server.py`, logic in `fetch/` and `nested/`)

| Tool | What the lead gets back |
|---|---|
| `chamber_fetch(url, instructions)` | A data file is saved to `data/raw/<nnn>-<name>` (named from the lead's URL, not a redirect target), and the lead gets the path plus the first 5 lines, framed. A page is turned into text in Python, then read by the tool-less extractor. The lead gets only the checked extract (framed), also saved to `extracts/<nnn>-<host>.md` with its URL and fetch date. |
| `chamber_extract_file(path, instructions)` | The same extractor over a text file inside the run folder. Paths outside it are refused. |
| `chamber_search(query)` | A nested session whose only tool is WebSearch, under `bypassPermissions` (without it the CLI denies WebSearch and the model answers an empty list). The lead gets `[{title, url, published_date?}]`, with no snippets. A turn with a permission denial or no usable results counts as a failed search. |
| `chamber_get_api_key(service, signup_url, env_var)` | A nested signup session (browser plus mail reads for the configured signup account, under security's `signup` role). Python checks the name and the key, then appends `ENV_VAR=key` to `<repo_root>/.env` while holding `.env.lock`. The lead gets only `{env_var, status, note}`, and the note is fixed text. The session runs under a session id chosen in Python, and its CLI transcript (which holds the key) is deleted with `claude_agent_sdk.delete_session` once it ends, ok or not. |

### Fetch rules (`fetch/`)

- Downloads honour robots.txt, 1 request/s per origin (shared across runs) and a 200 MB cap.
- The robots.txt cache and the rate limiter both key on `origin_key(url)`: scheme, lowercased hostname and port (the scheme's default if none is given). So `EX.org` and `ex.org:443` are one origin, and http and https on one host are two.
- robots.txt is fetched with our User-Agent, a 15 s timeout and a 512 KiB cap. Per RFC 9309, a 4xx means allow-all. A 5xx or an unreachable host refuses that call and isn't cached.
- Redirects are followed by hand, at most 5, and every hop is checked again: http(s) only, robots.txt, the rate limit.
- The server's content type is cut to a bare `type/subtype`, or "" if it isn't one. It isn't trusted on its own: a body that starts with `<` is always a page, and a JSON type must parse, else it's a page. A body with no type or `application/octet-stream` and no data-file extension is a page if it's UTF-8 with no NULs, so prose can't land in `data/raw/`.
- Error text the lead sees is fixed (`HTTP 404`, an exception type name), never server text. `HttpDownloader.__call__` and `RobotsCache.allows` are catch-all boundaries: any other exception is logged and becomes `FetchError("bad URL or response (<Type>)")` (`http.unexpected_error`). Cancellation still propagates.

### Failures

No exception escapes a tool handler, since the SDK would pass its text to the lead. Every nested session's output is held to a JSON schema and then checked again in Python (`nested/`), so prose outside the schema never reaches the lead. Any fetch or extractor failure, timeout included, fails closed: the lead gets an error naming the source, and the raw content is withheld. Unexpected errors are logged in the daemon (signup logs only the type, never the key). Each source goes to `on_source(record)` as `{name, url, status, note, fetched_at}`; an exception from `on_source` is logged and never escapes a handler. By default the record is appended to `ctx.manifest.sources` in memory, and the agents never write the manifest.

### Signup name rules (`nested/envfile.py`)

Every Signal MCP server runs with `--env-file .env`, so a name written there reaches all of them. The name must:

- end in `_API_KEY`, `_KEY` or `_TOKEN`;
- not start with `PATH`, `PYTHON`, `SSL_`, `REQUESTS_`, `CURL_`, `UV_`, `PIP_`, `ANTHROPIC_`, `CLAUDE_`, `NODE_`, `GIT_`, `GH_`, `GITHUB_`, `HTTP`, `SIGNAL_`, `CHAMBER_` or `OTEL_`, and not contain `PROXY`;
- not be set already in `os.environ` or in `.env` (`NAME=`, `NAME =` or `export NAME`), compared case-insensitively as Windows does.

The key can't contain `:`, `/`, spaces, quotes or line breaks.

## Signal free-text swap (`fetch/signal_swap.py`)

A PostToolUse hook on every MCP tool except the chamber's own and `PASS_THROUGH_TOOLS`: `mail_accounts` (aliases and addresses) and `rcs_status` (pairing, phone, last sync, daemon state). The list is inverted so a new free-text tool gets swapped by default. The hook saves the raw output to `data/raw/signal/<nnn>-<tool>.txt`, runs the extractor, and replaces the output through `updatedMCPToolOutput`. If anything fails, the output becomes `WITHHELD`. The extractor's timeout is shorter than the hook's, so ours fires first.

A result with `isError` fires PostToolUseFailure instead. In SDK 0.2.168 that event's output has only `additionalContext` (the bundled CLI reads nothing else for it), so it can't replace or withhold the error text. `signal_failure_matcher` adds a fixed warning on the same tools that the error text is untrusted data. TODO: the error text itself still reaches the lead. Swap it once the CLI lets PostToolUseFailure replace output, or have Signal's servers put only fixed text in `isError` results.

## Run-folder files (`fetch/store.py`)

Files in `extracts/` and `data/raw/` are numbered one past the highest existing `<nnn>-` prefix. Each is created exclusively, with a retry if another writer took the number first.

## MCP tool-call timeout

`chamber_get_api_key` can run for up to 15 min. The bundled CLI (SDK 0.2.168) takes the server's `timeout`, else `MCP_TOOL_TIMEOUT`, else a default of 1e8 ms (about 28 h). SDK servers have no idle timeout, and the SDK control channel puts no timeout on tool-call requests. So the lead env sets nothing.

## Depends on

`config`, `runs`, `guard` (`is_under`), `security`, `kit` (`run_env`), `claude-agent-sdk`, `signal-untrusted`, `signal-jsonstate` (the `.env` lock).
