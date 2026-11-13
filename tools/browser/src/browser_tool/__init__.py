"""browser_tool: a Playwright MCP server that lets Claude drive Microsoft Edge safely.

The server lives in `browser_tool.server` (entry point `browser-tool`). The other
subpackages are the building blocks it wires together: config, policy (domain
allow/deny), redaction (password/OTP hiding), gates (owner confirmation),
credentials (vault adapter), session (browser lifecycle) and actions (one
function per MCP tool). visit is a second entry point (`browser-tool-visit`) that
visits a fixed plan of pages with no model. See README.md in each subpackage.
"""
