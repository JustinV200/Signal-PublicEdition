"""Layer 2's deny-by-default data: the MCP tools each chamber role may call.

Chamber sessions load only explicit MCP servers (strict_mcp_config), and send_block_hook
denies any mcp__ tool not listed here for the calling role. The chamber's own
in-process server (mcp__chamber__*) is always allowed. The agents builder should load
only the servers these names belong to (see mcp_servers_for).
"""

from analysis_chamber.security.rules.tool_lists import BROWSER_ACTIONS

CHAMBER_SERVER_PREFIX = "mcp__chamber__"

_MAIL_READS = (
    "mcp__mail__mail_accounts",
    "mcp__mail__mail_search",
    "mcp__mail__mail_read",
    "mcp__mail__mail_thread",
)

# Read-only Signal tools for the lead's data collection (spec 12). Calendar, vault,
# jobhunt and usage have no MCP server yet; add their read tools here when they do.
_LEAD_READS = (
    *_MAIL_READS,
    "mcp__rcs__rcs_status",
    "mcp__rcs__rcs_conversations",
    "mcp__rcs__rcs_read",
    "mcp__rcs__rcs_search",
    "mcp__brief__brief_get",
)

# The signup sub-agent: a browser (no uploads, no owner sign-ins) for free API-key
# signups, plus mail reads limited to config.signup_mail_account for verification mails.
# It prefers the throwaway docker browser; the desktop one is the fallback when the
# docker server isn't configured (signup.py loads only one of them). Purchases are
# gated by the browser tool itself (it waits for the owner's approval).
_SIGNUP_TOOLS = (
    *("mcp__browser-docker__" + name for name in BROWSER_ACTIONS),
    *("mcp__browser__" + name for name in (*BROWSER_ACTIONS, "read_download")),
    *_MAIL_READS,
)

MCP_ALLOWLISTS: dict[str, tuple[str, ...]] = {
    "lead": _LEAD_READS,
    # Critic and Q&A work from the run folder and the chamber tools only.
    "critic": (),
    "qa": (),
    "signup": _SIGNUP_TOOLS,
}
