"""Model-facing text for the sessions MCP server: server instructions and tool descriptions.

A calling model sees only these strings, so each says what the tool does,
when to use it (and when to use Claude Code's built-in ListAgents/SendMessage
instead), what the arguments mean and what comes back.
"""

SERVER_INSTRUCTIONS = (
    "sessions starts and drives headless Claude Code sessions in the owner's local git repos "
    "(under C:\\src) through a background daemon, and lists past Claude Code sessions so "
    "they can be resumed. Use it to hand work to a separate Claude Code session in another "
    "repo. For a session that is already open live (VS Code, a terminal, Remote Control or "
    "the cloud), use the built-in ListAgents and SendMessage tools instead: these tools only "
    "drive sessions this daemon runs. Managed sessions load the owner's normal settings, ask "
    "the owner to approve risky tool calls in a dialog on the PC (denied after 120 s), and "
    "announce finished turns through the voice hub."
)

LIVE_SESSIONS_NOTE = (
    "Not for sessions open live in VS Code, a terminal, Remote Control or the cloud: reach "
    "those with the built-in ListAgents and SendMessage tools."
)

LIST_REPOS = """List the owner's local repos under C:\\src: git repos, plus folders where Claude
Code has already run (is_git false), such as a project folder holding a repo one level down.

Use it to find the repo name or path to pass to start_session or list_sessions.

Args:
    query: Optional case-insensitive filter on repo name or path; "" lists all.

Returns JSON: [{"name", "path", "is_git"}], sorted by name."""

LIST_SESSIONS = f"""List existing Claude Code sessions (from ~/.claude/projects), newest first.

Use it to find a past session to continue with resume_session, e.g. "pick up where I left
off in OtherRepo". Covers every session ever run, managed or not.

Args:
    repo: A repo path or unique name match; "" lists the newest sessions across all repos.

Returns JSON: [{{"session_id", "last_modified", "first_prompt", "title", "cwd"}}], at most 20
(cwd only when repo is ""; null fields are left out).
{LIVE_SESSIONS_NOTE}"""

START_SESSION = f"""Start a new headless Claude Code session in a local repo with a first prompt.

Use it to delegate a task to a separate Claude Code session working in another repo. It
returns at once with the session's id while the session works in the background; check
on it with session_status (the voice hub also announces when the turn finishes).

Args:
    repo: A repo path, or a repo name or unique part of one (see list_repos).
    prompt: The task, written as you would type it into Claude Code there.
    model: Optional model or alias, e.g. "sonnet" or "opus"; "" uses the owner's default.
    permission_mode: "default" (ask the owner about risky tool calls), "acceptEdits"
        or "plan" (read-only planning). acceptEdits runs file edits, the Bash commands
        mkdir, touch, rm, rmdir, mv, cp and sed, AND the PowerShell cmdlets Set-Content,
        Add-Content, Clear-Content and Remove-Item (and their aliases) on paths inside
        the repo without asking, so it can delete or overwrite files unapproved; other
        calls still ask. Use it only when the owner
        asked for it. bypassPermissions is never allowed.

Returns JSON status: {{"id", "repo", "state", "claude_session_id", ...}}.
{LIVE_SESSIONS_NOTE}"""

SEND_TO_SESSION = f"""Send a follow-up prompt to a running managed session.

Use it after session_status shows the session "idle" (or "error" while still live), to
continue the conversation. A busy session refuses the prompt; a stopped one must be
continued with resume_session instead.

Args:
    id: The managed session id from start_session or list_managed_sessions.
    prompt: The next user message.

Returns JSON status (state "working").
{LIVE_SESSIONS_NOTE}"""

SESSION_STATUS = """Check on a managed session: its state, cost and newest replies.

States: "working" (running a turn), "awaiting_permission" (a tool call waits for the
owner's dialog; pending_approval says which), "idle" (turn done; send more), "error"
(see error), "stopped" (no process; resume_session continues it).

Args:
    id: The managed session id.
    last_n: How many of the newest assistant texts to include (0-10, default 1).

Returns JSON status with last_texts oldest first; null fields are left out."""

RESUME_SESSION = f"""Continue an existing Claude Code session headlessly with a new prompt.

Use it for a managed session that is stopped (after stop_session or a daemon restart), or
to adopt any past session from list_sessions. It runs in the folder the session ran in,
with its full history. Don't resume a session that is still open elsewhere: two writers
on one transcript conflict.

Args:
    claude_session_id: A Claude session id from list_sessions, or a managed id.
    prompt: The user message to continue with.

Returns JSON status (state "working").
{LIVE_SESSIONS_NOTE}"""

STOP_SESSION = """Stop a managed session's Claude Code process.

Use it when the session's work is done or should be abandoned. Its transcript stays, and
resume_session can continue it later.

Args:
    id: The managed session id.

Returns JSON status (state "stopped")."""

LIST_MANAGED_SESSIONS = f"""List the sessions this daemon manages, newest first: the 10 newest
plus any older one that is still live.

Use it to find a managed session's id, or to see what is still running.

Returns JSON: [{{"id", "repo", "state", "is_live", "claude_session_id", "cost_usd", ...}}].
{LIVE_SESSIONS_NOTE}"""
