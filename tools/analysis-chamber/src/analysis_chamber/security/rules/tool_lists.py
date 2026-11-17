"""The send block's layer 1 data: built-ins, outbound tools and every known Signal MCP tool.

Under bypassPermissions `allowed_tools` restricts nothing, so the allowlist is enforced
by denying instead: disallowed_tools(role) lists OUTBOUND_TOOLS, BUILTIN_DISALLOWED,
every whole server a role has no allowed tool on, and every other known tool of the
servers it partly uses (SIGNAL_SERVER_TOOLS). send_block_hook (layer 2) then denies any
mcp__ tool not on the role's allowlist, which also catches tools added after this list.
The tool-isolation spike (notes not published)
showed both layers hold under bypassPermissions, and that a bare `mcp__server` entry or
a trailing-`*` prefix glob blocks a whole family. Update SIGNAL_SERVER_TOOLS when a
Signal MCP server gains a tool.
"""

# Built-in Claude Code tools. WebFetch and WebSearch are out for every role: pages and
# search results go through the chamber's fetch/search tools so agents only see
# extracts (spec 7.2, 13).
# The rest notify, message, publish or schedule; names checked against the bundled CLI
# (claude-agent-sdk 0.2.168, CLI 2.1.301). Left allowed on purpose: CronList, TaskStop,
# ListAgents, ReadNotifications and FetchInboxMessage (reads), and the worktree tools.
BUILTIN_DISALLOWED = (
    "WebFetch",
    "WebSearch",
    "SendMessage",  # messages another live session
    "SendFile",  # sends files to another session
    "SendUserMessage",  # messages the user directly
    "SendUserFile",
    "PushNotification",  # the daemon notifies, never the run
    "RemoteTrigger",
    "Artifact",  # publishing is done by the starting chat, never the run (spec 12)
    "ArtifactCheck",
    "ArtifactComments",
    "ArtifactData",
    "PublishPlugin",
    "CronCreate",  # schedules work that runs after the run, outside its hooks' reach
    "CronDelete",
    "ScheduleWakeup",
    # Monitor runs a background shell command; the shell hooks only see Bash and
    # PowerShell, so it would get around them.
    "Monitor",
)

# Send, post, publish, delete and owner-state tools, denied for every role whatever the
# allowlists say. A test checks no allowlist contains one.
OUTBOUND_TOOLS = (
    "mcp__mail__mail_draft",
    "mcp__mail__mail_send_draft",
    "mcp__rcs__rcs_send*",  # rcs is read-only today; this catches the send tool when it lands
    # brief: logging, resolving and acks change the user's brief (the daemon notifies);
    # brief_me records a delivery.
    "mcp__brief__brief_log",
    "mcp__brief__brief_resolve",
    "mcp__brief__brief_ack",
    "mcp__brief__brief_undo",
    "mcp__brief__brief_me",
    "mcp__brief__away_on",
    "mcp__brief__away_off",
    # sessions: starting or driving another Claude session is outbound.
    "mcp__sessions__start_session",
    "mcp__sessions__send_to_session",
    "mcp__sessions__resume_session",
    "mcp__sessions__stop_session",
    # browser: uploads send local files out; fill_login signs in as the user.
    "mcp__browser__upload_file",
    "mcp__browser__fill_login",
    "mcp__browser__list_credentials",
    "mcp__browser-docker__upload_file",
    # The run must not speak (the daemon notifies), draw on the board or toggle sleep.
    "mcp__audiohub",
    "mcp__whiteboard",
    "mcp__sleepmode",
    # claude.ai connectors (Gmail send/reply/forward/trash, Calendar create/delete, Docs
    # publishing). strict_mcp_config keeps them out anyway; the spike found they load
    # even with setting_sources=[]. Whole servers: Signal's mail tool is the read path.
    "mcp__claude_ai_Gmail",
    "mcp__claude_ai_Google_Calendar",
    "mcp__claude_ai_Claude_Docs",
    "mcp__claude_ai_Google_Drive",
    # Any other connector. The spike verified prefix globs within one server only, so
    # the known ones are also named above; layer 2 denies the rest either way.
    "mcp__claude_ai_*",
    # The chamber's own stdio server (register.ps1 adds it to .mcp.json): a run must not
    # start, approve or cancel runs. Its in-process tools are mcp__chamber__*.
    "mcp__analysis-chamber",
)

BROWSER_ACTIONS = (
    "navigate", "back", "forward", "reload", "new_tab", "close_tab", "switch_tab", "tabs",
    "snapshot", "screenshot", "find", "click", "click_at", "hover", "drag", "type_text",
    "press_key", "select_option", "scroll", "wait_for", "wait_for_duo", "answer_dialog",
)  # fmt: skip

# Every tool of each .mcp.json server (from tools/*/src/**/mcp_server).
SIGNAL_SERVER_TOOLS: dict[str, tuple[str, ...]] = {
    "mail": (
        "mail_accounts", "mail_search", "mail_read", "mail_thread", "mail_draft",
        "mail_send_draft",
    ),
    "rcs": ("rcs_status", "rcs_conversations", "rcs_read", "rcs_search"),
    "brief": (
        "brief_me", "brief_get", "brief_log", "brief_ack", "brief_resolve", "brief_undo",
        "away_on", "away_off", "away_status",
    ),
    "sessions": (
        "list_managed_sessions", "list_repos", "list_sessions", "resume_session",
        "send_to_session", "session_status", "start_session", "stop_session",
    ),
    "browser": (*BROWSER_ACTIONS, "fill_login", "list_credentials", "read_download", "upload_file"),
    "browser-docker": BROWSER_ACTIONS,
    "audiohub": (),  # whole server denied in OUTBOUND_TOOLS
    "whiteboard": (),
    "sleepmode": (),
    "analysis-chamber": (),
}  # fmt: skip

# Extra built-ins per role. The signup sub-agent only drives the browser and reads the
# signup mailbox, so it gets no shell.
ROLE_EXTRA_DISALLOWED: dict[str, tuple[str, ...]] = {
    "lead": (),
    "critic": (),
    "qa": (),
    "signup": ("Bash", "PowerShell"),
}

ROLES = frozenset(ROLE_EXTRA_DISALLOWED)
