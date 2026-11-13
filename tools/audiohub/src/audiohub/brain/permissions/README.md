# audiohub.brain.permissions

Decides whether a tool call from the voice brain may run. Voice is a thin, fast layer (music,
the whiteboard, the brief, sleep mode, quick lookups); everything else goes to the main Signal
session through the hand-off tool. So the gate never asks a question: it allows voice's own
tools and refuses the rest quietly. It doesn't import the SDK; `audiohub.brain.sdk_options`
adapts it to `can_use_tool`.

## Public API

- `PermissionGate(auto_allow_tools, project_root, *, auto_allow_mcp_servers=())`:
  `await decide(request) -> PermissionDecision`. Both lists come from `[brain]` in the config.
  - **Allowed** (logged at INFO with resolved paths):
    - tools named exactly in `auto_allow_tools`. Default: Read, Glob, Grep, WebSearch, and the
      read-only mail and sessions tools (`mail_accounts`, `mail_search`, `mail_read`,
      `mail_thread`, `list_sessions`, `list_managed_sessions`, `list_repos`, `session_status`),
      and the brief (`brief_me`, `brief_get`, `brief_ack`, `brief_resolve`, `away_on`,
      `away_off`, `away_status`). `brief_log` and `brief_undo` are left out, so text voice
      reads in mail or on the web can't log a trusted brief entry or undo one.
    - every tool of a server named in `auto_allow_mcp_servers`
      (`mcp__<server>__<snake_case_name>`, exact server name). Default: audiohub, whiteboard,
      sleepmode. Look-alikes such as `audiohub_x` or `audiohub__evil` don't count.
    - the hand-off, `mcp__voice__hand_off_to_main_session` (`ALWAYS_ALLOWED_TOOLS`), whatever
      the config says. No one approves it by voice, so the message it sends keeps the owner's
      verbatim words apart from the model's summary and tells the orchestrator to treat a
      summary that doesn't match them as suspect (`../handoff_tool/`).
  - **Refused quietly**, with `MAIN_SESSION_HANDOFF_MESSAGE` as the tool result, which tells
    Claude to hand the job off: everything else. That covers Bash, PowerShell, file writes,
    WebFetch, the browser servers, mail drafts and sends, starting, stopping or messaging
    sessions, `brief_log` and `brief_undo`, and any unknown tool or server. `sdk_options.VOICE_TOOLS` already leaves the
    shell, write and fetch built-ins out of the session; the gate is the second layer, and the
    only one for MCP tools.
  - **Secrets** (`secret_paths.py`): a Read, Glob or Grep of `.env`, `.env.*`, `*.env`, any
    `.state/` or `.cache/` folder, `tools/browser/.profile/` and `.screenshots/`, or, in the
    home folder, `~/.ssh/`, `~/.claude/.credentials.json`, `~/.claude/ide/`, the vault store,
    `.git-credentials`, `.config/gh`, `AppData/Roaming/GitHub CLI`, `.aws`, `.npmrc`,
    `.docker/config.json`, `.kube`, `.azure`, `AppData/Roaming/gcloud`, `.config/gcloud`,
    Claude Code's session transcripts (`.claude/projects`) and the real browser profiles
    (Edge, Chrome, Firefox, Brave) is refused with `SECRET_READ_REFUSAL`. `SECRET_READ_DENY_RULES` turns the lists into CLI
    deny rules (`disallowed_tools`) that stop plain reads before the gate; the gate catches
    what they miss, such as the 8.3 alias `ENV~1`, by resolving the path (`tool_paths.py`).
    Paths are resolved on the filesystem (`os.path.realpath`), so short names, junctions and
    symlinks are followed; a NUL, an alternate data stream, a part ending in "." or " ", a UNC
    or device path, or a failed resolve counts as secret (fails closed).
  - Every tool call reaches the gate: `sdk_options`' PreToolUse hook answers "ask" for every
    tool. The account's claude.ai connectors (Gmail, Docs, Calendar) are off
    (`disableClaudeAiConnectors`), so voice has no calendar tool.
- `PermissionRequest(tool_name, tool_input)`, `PermissionDecision(is_allowed, refusal=None)`,
  and the type alias `PermissionDecider`.
- `is_auto_allowed(tool_name, auto_allow_tools, auto_allow_mcp_servers)`: the name check alone.
- `SECRET_READ_DENY_RULES`: the CLI permission rules for the secret paths.

## Modules

| Module | Role |
|---|---|
| `gate.py` | `PermissionGate`, the allow/refuse rules |
| `secret_paths.py` | which paths hold secrets, as a check and as CLI deny rules |
| `tool_paths.py` | which paths a call targets, and resolving them |

## Limits

- WebSearch results and mail voice reads may carry instructions written by others. Voice can
  act on them only through its own tools (music, the board, the brief) and the hand-off, whose
  message labels the summary as the model's and keeps the owner's words beside it.
- A WebSearch query is sent to the search provider, so text voice has read can leave the PC
  that way.

## Depends on

The standard library, and `audiohub.brain.handoff_tool` for the hand-off tool's names.
