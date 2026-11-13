# Browser control for Claude Code and audiohub

Researched 2026-10-19. Sources are inline. Anything marked **[unverified]** came from a secondary source, or from a fetch whose summary left it out.
The vault doc (`password-vault.md`) did not exist yet when I wrote this. The vault integration below assumes only an opaque `credential_id`.

## 1. Options

| Option | Runtime | How Claude drives it | Profile / sessions | License | Windows |
|---|---|---|---|---|---|
| Playwright MCP (`@playwright/mcp`) | Node 18+ (confirmed) | Accessibility-tree snapshots by default. `--caps=vision` adds coordinate tools. | Persistent profile by default (`ms-playwright/mcp-{channel}-{workspace-hash}` under the OS cache dir; README lists Linux/macOS paths, Windows path not confirmed) (corrected in review). `--isolated`, `--storage-state`, `--cdp-endpoint`, and `--extension` (attach to running Chrome/Edge). | Apache-2.0 | Yes. `--browser msedge` works. |
| Chrome DevTools MCP | Node LTS (confirmed) | DevTools-oriented tools (console, network, perf, DOM, screenshots). | Server-specific profile by default. Can attach to a running Chrome (see section 2). Officially supports only Chrome and Chrome for Testing. | Apache-2.0 | The README does not mention Windows. **[unverified]** |
| Claude in Chrome extension | Chrome/Edge extension plus a native-messaging host launched by Claude Code | Claude Code exposes `mcp__claude-in-chrome__*` tools. Tabs go into a Chrome tab group. | Your real browser and its logins. Per-site permission prompts. | Proprietary Anthropic product | Yes. Named-pipe and native-host issues are documented. |
| browser-use (Python) | Python 3.11+ | Its own LLM agent loop over CDP. Not an MCP server out of the box. | `Browser.from_system_chrome()` reuses a Chrome profile. Remote CDP is supported. | MIT | Yes **[unverified]** |
| Playwright for Python + our own MCP | Python 3.12 + uv, no Node | We define the tools (`goto`, `snapshot`, `click`, `fill_login`, ...). | Anything Playwright supports: persistent context, `connect_over_cdp`, storage state. | Apache-2.0 | Yes |
| Stagehand | TS, Python and Go SDKs | `act`, `observe` and `extract` natural-language primitives. Needs its own LLM key. | Local Chrome with `userDataDir`, or hosted Browserbase. | MIT | Likely **[unverified]** |

Sources:
- Playwright MCP: https://github.com/microsoft/playwright-mcp
- Chrome DevTools MCP: https://github.com/ChromeDevTools/chrome-devtools-mcp
- Claude in Chrome, and how Claude Code uses it: https://code.claude.com/docs/en/chrome
- browser-use: https://github.com/browser-use/browser-use
- Stagehand: https://github.com/browserbase/stagehand

### Reliability, token cost, maintenance

- **Playwright MCP.**
  - It is the most widely used option, and Microsoft maintains it.
  - Snapshots are text, so it needs no vision model.
  - Token cost: a full snapshot per action is large on busy pages. `--snapshot-mode` can reduce it. I have no measured numbers.
  - Reliability is good because elements are addressed by ref, not by pixel.
- **Chrome DevTools MCP.**
  - It is built for debugging and performance, not for general task automation.
  - It collects usage statistics by default. Opt out with `--no-usage-statistics` or the `CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS` env var (corrected in review). Separate flags cover CrUX and update checks.
  - It is not a good fit for login and forms.
- **Claude in Chrome.**
  - It is the lowest setup, with the real browser, real sessions and a visible window.
  - Requirements: a Pro/Max/Team/Enterprise plan, and `/login` auth. It stays off with an API key or `setup-token`.
  - It is not available through Bedrock, Vertex or Foundry.
  - Claude Code and VS Code reach it via `claude --chrome` or `@browser`.
  - Enabling it by default adds browser tool definitions to every session's context.
  - It is a closed box. We cannot inject our own page-level `fill_login` into it, and **it cannot be used from the Agent SDK in audiohub** **[unverified]**. The docs describe only the CLI and the VS Code extension.
  - Anthropic describes classifiers for prompt injection and for per-action checks. It also lists actions that are off-limits, such as purchases, account creation and permanent deletes: https://support.claude.com/en/articles/12902446-claude-in-chrome-permissions-guide
  - A third-party write-up reported a zero-click injection that was fixed in extension 1.0.41 **[unverified, secondary]**.
- **browser-use.**
  - It is very active (about 118k stars). But it runs its own agent loop with its own LLM calls, which duplicates Claude.
  - It has a `sensitive_data` parameter, but I could not confirm what the model sees. Check `examples/features/sensitive_data.py` before relying on it.
  - It is a poor fit when Claude is the driver. It could serve as a library, but it adds a lot of surface.
- **Stagehand.**
  - It targets TS first and runs its own LLM calls, so the same duplication applies.
  - Its README claims `observe()` returns selectors so credentials never reach the model **[unverified claim]**.
  - Its hosted mode is geared to Browserbase cloud, which is not our use.

## 2. Profiles and sessions

- **Dedicated automation profile (recommended default).**
  - Playwright MCP's persistent `--user-data-dir`, or our own `launch_persistent_context(user_data_dir=...)`. Log in once, and cookies persist on disk.
  - One browser instance per profile at a time (Playwright MCP README).
  - Isolated modes (`--isolated`, `--storage-state`) are in-memory, or loaded from a state file. Never write the storage-state file into the repo, because it contains live session cookies.
- **Attaching to the daily Chrome over CDP.** Chrome 136+ ignores `--remote-debugging-port` and `--remote-debugging-pipe` when pointed at the default user-data-dir. The block exists to stop cookie theft. See https://developer.chrome.com/blog/remote-debugging-port.
  - So "just attach to my normal Chrome" no longer works by flag. Workarounds:
    - Launch Chrome with a non-default `--user-data-dir`. That makes it a dedicated profile.
    - Use the `chrome://inspect/#remote-debugging` toggle plus a user Allow dialog. Chrome DevTools MCP's `--autoConnect` uses this. It needs Chrome 144+, and Chrome shows an "automated test software" banner: https://developer.chrome.com/blog/chrome-devtools-mcp-debug-your-browser-session
    - Use an extension (Playwright Extension via `--extension`, or Claude in Chrome). Extensions run inside the real profile.
  - Edge is Chromium. The Chrome blog does not mention Edge, so whether Edge applies the same restriction is unverified. A custom `--user-data-dir` is the documented way to keep debugging working, which matches our dedicated profile (confirmed in review).
- **Cookie persistence.**
  - Dedicated profile: automatic.
  - Playwright `storage_state()` gives cookies plus localStorage. It does not cover IndexedDB or extensions.
  - browser-use cloud profile sync copies cookies only.
- **Security implications of the daily profile.**
  - The agent inherits every login: mail, banking, cloud consoles, the password manager's web UI. One injected instruction on one page gets the owner's full authority.
  - Claude in Chrome's own docs say it "shares your browser's login state, so it can access any site you're already signed into".
  - Prefer a dedicated profile, logged into only the accounts the owner wants automated. Use a separate low-privilege or dedicated account where a site allows it.
  - Keep that profile's `user-data-dir` out of the repo and out of backups.

## 3. Safety controls

- **Domain allow/deny.**
  - Playwright MCP has `--allowed-origins` and `--blocked-origins`. The blocklist is evaluated first. The README says these are **not a security boundary** and do not cover redirects.
  - Claude in Chrome has per-site permission (allow for good, allow once, or deny), set in the extension: https://support.claude.com/en/articles/12902446-manage-claude-in-chrome-permissions
  - In our own server we can enforce an allowlist with `context.route("**/*", ...)`. This also covers subrequests and redirects. We can check the host again after every navigation.
- **Confirmation before sensitive actions.**
  - Neither Playwright MCP nor DevTools MCP has built-in human-in-the-loop for purchases, sends or deletes.
  - Claude Code's permission prompts per MCP tool are the only gate. They are too coarse once a click tool is approved.
  - Our server can classify each click/submit and require explicit confirmation. Signals: button text matching buy, pay, send, delete or confirm; the domain; a form `POST`.
  - Confirmation should be out of band from the model. In audiohub that is a spoken yes/no. In VS Code it is the approval prompt.
- **Prompt injection.**
  - Page text goes straight into model context in every option. No tool "solves" this.
  - Mitigations:
    - Allowlist domains, so the agent cannot wander to attacker pages.
    - Mark page content as untrusted in the tool result (a wrapper like `<untrusted_page_content>`).
    - Gate high-impact actions as above.
    - No file-upload or download tools without confirmation. Playwright MCP limits file access to workspace roots and blocks `file://` by default.
    - Avoid `browser_run_code_unsafe`. The README calls it RCE-equivalent.
- **Keeping credentials out of snapshots and screenshots.**
  - Playwright MCP's README does **not** say password inputs are masked in snapshots **[unverified]**. Test this ourselves before relying on it, including `type=password` and OTP fields.
  - Playwright MCP's `--secrets` is text replacement in tool output. The README calls it "a convenience and not a security feature".
  - Screenshots show whatever is rendered. A masked password field shows dots, but a "show password" toggle, an autofilled username, or a 2FA code would be visible.
  - In our own server we control the output. We never return `input.value`, we redact or blur password and OTP fields before any screenshot, and `fill_login` returns only `ok` or `failed(reason)`.

## 4. Recommendation

**Build a thin Python Playwright MCP server in `tools/browser`. Keep Claude in Chrome as an optional, separate way to do ad-hoc work in the real browser.**

Why:
- The machine has no Node. Playwright MCP, DevTools MCP and Stagehand's TS SDK would all need an install. Python + uv is already present.
- The vault needs code-level page access in our process. The off-the-shelf MCP servers have no hook for it. Playwright MCP's `browser_type` and `browser_fill_form` would pass the secret through the model.
- We control allowlists, confirmation gates and output redaction, which the third-party servers leave to us.
- Cost: we must write snapshot and ref logic. Playwright for Python has `Locator.aria_snapshot(mode="ai")`, which returns `[ref=e2]` refs valid only for the latest snapshot, and `page.get_by_ref("e2")` (verified in review against https://playwright.dev/python/docs/api/class-locator; confirm `Page.aria_snapshot` on your installed version) (corrected in review). Keep the tool set small:
  - `goto(url)`
  - `snapshot()`, an aria snapshot with element refs
  - `click(ref)`
  - `fill(ref, text)`, for non-secret text only
  - `press(key)`
  - `screenshot()`, redacted
  - `fill_login(credential_id)` (corrected in review, matches the sketch)
  - `tabs`, and `close`

Hybrid note: if the owner wants a zero-code fallback, Playwright MCP via `npx` after installing Node (corrected in review) is the best off-the-shelf option. We would still need the vault hook as a separate step.

### Vault integration

`fill_login` is a tool the model can call, but whose result it cannot read:

```python
# tools/browser/login.py  (sketch, not implemented)
async def fill_login(page, credential_id: str) -> dict:
    cred = vault.resolve(credential_id)        # in-process only, never returned
    if not origin_matches(page.url, cred.origin):   # block phishing and redirect mismatch
        return {"ok": False, "reason": "origin_mismatch"}
    user_loc, pass_loc = find_login_fields(page)   # heuristics in our code, not model-supplied (corrected in review)
    await user_loc.fill(cred.username)
    await pass_loc.fill(cred.password)
    return {"ok": True}                        # no values, no field text, no screenshot
```

Rules:
- The origin check uses the credential's stored origin against the live `page.url` (after redirects). The model cannot talk the tool into filling a lookalike domain.
- The model passes only `credential_id` or a site name. It never sees the username either, if the vault says usernames are secret.
- Selector discovery for username and password fields happens inside our code (heuristics on `input[type=password]`). The model is not asked to supply selectors.
- After filling, the model clicks submit through the normal `click(ref)` tool, or `fill_login(..., submit=True)` does it. 2FA codes come from the vault the same way, as `fill_otp`.
- Any snapshot taken immediately afterward redacts password and OTP inputs.
- Log the credential id and the origin, never values.

### audiohub

- The audiohub voice assistant runs on the Claude Agent SDK. It can register the server as a stdio MCP server (`mcp_servers={"browser": {"command": "uv", "args": [...]}}`). I did not check the SDK's exact option shape **[unverified]**. The official `mcp` Python SDK supports stdio. Pin `mcp<2`: v1.x uses `from mcp.server.fastmcp import FastMCP` and its README pins `mcp<2`, while the main-branch README shows a renamed `MCPServer` (corrected in review; https://github.com/modelcontextprotocol/python-sdk). On stdio, never `print()` to stdout. Log to stderr **[unverified for this SDK]**. Claude Code in VS Code uses the same server via `.mcp.json`.
- Voice-specific points:
  - Spoken confirmation for gated actions ("Buy this for $42 from X? Say yes or no"). The gate lives in the server, so a mis-heard "yes" is the only failure mode.
  - Keep tool results short. Return a trimmed snapshot (visible interactive elements only) so the voice loop stays fast.
  - Never read page text aloud blindly, because injected text can contain instructions.
  - The server can run headless for background jobs. Run it headed whenever a login or CAPTCHA needs the owner (pause, and ask them to handle it, as Claude in Chrome does).

## 5. Owner decisions and setup

1. **Browser.** Chrome or Edge? Playwright drives Edge through `channel="msedge"`, so no download is needed. Chrome for Testing is Google's recommended automation browser.
2. **Dedicated profile (recommended) or daily profile?**
   - Dedicated: a one-time manual login for each site, kept in something like `%LOCALAPPDATA%\signal-browser\profile`.
   - Daily: not directly possible by CDP flag on Chrome 136+. It needs an extension, and it exposes everything.
3. **Which accounts and sites are in scope.** That becomes the initial allowlist.
4. **Which actions always need a spoken or typed confirmation.** The default proposal is anything that spends money, sends a message, or deletes.
5. **Node.** Not needed for the recommended build. Needed only if the owner wants Playwright MCP or DevTools MCP off the shelf.
6. **Claude in Chrome.** Optional. Needs a claude.ai plan with `/login` auth (not an API key), plus the Chrome Web Store extension, version 1.0.36 or later. The owner decides whether to allow it for ad-hoc tasks alongside our tool.
7. **Setup steps for the build.**
   - `uv add playwright "mcp<2"`. Skip `playwright install`: `channel="msedge"` uses the installed Edge (https://playwright.dev/python/docs/browsers). Enterprise browser policies can interfere (corrected in review).
   - Create the profile folder.
   - Run a headed login once.
   - Register the server in `.mcp.json` and the audiohub config.

## Risks

- Prompt injection can never be fully eliminated. The allowlist plus action gates reduce the damage but do not close it.
- Snapshot masking of password fields is untested. Test it before first use.
- A persistent profile holds live session cookies on disk, so treat the folder as a secret.
- Sites with bot detection may block Playwright-driven browsers. Not tested.
- The Chrome behavior around the default profile may change again. Re-check before depending on attach-to-daily.
