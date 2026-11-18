"""collect_tools_text: the short list of what the collect phase can use, for the plan prompt.

The plan turn has no tools, so it can't see what the lead gets later. This builds the list
from the real config, so it can't drift: the Signal servers actually present in .mcp.json
(filtered by the lead's allowlist), the chamber tools, and whether a signup account is set.
"""

from analysis_chamber import security
from analysis_chamber.agents.context import RunContext
from analysis_chamber.agents.options.prompts import FETCH_TOOL, KEY_TOOL, SEARCH_TOOL
from analysis_chamber.agents.signal_mcp import load_signal_servers


def collect_tools_text(ctx: RunContext) -> str:
    """A Markdown bullet list of the sources and tools the collect phase can use."""
    lines = [
        f"- Web search ({SEARCH_TOOL}) and page fetch ({FETCH_TOOL}); pages come back as extracts.",
        "- Public data APIs and data files (CSV, JSON), downloaded straight into data/raw. "
        + _api_key_line(ctx),
    ]
    signal = _signal_line(ctx)
    if signal:
        lines.append(signal)
    lines += [
        "- Files the user names in the question (read into the run folder).",
        "- The analysis kit: a Python data/stats/ML environment; GPU steps run through "
        "`analysis-chamber gpu`.",
    ]
    return "\n".join(lines)


def _api_key_line(ctx: RunContext) -> str:
    """Whether a free API key can be obtained, which depends on the signup mailbox."""
    if ctx.config.signup_mail_account:
        return f"Keyless sources are preferred; a free key can be signed up for ({KEY_TOOL})."
    return "Keyless sources only: no signup account is configured, so keys can't be obtained."


def _signal_line(ctx: RunContext) -> str:
    """The Signal read tools whose servers are present, grouped by server; "" if none."""
    present = load_signal_servers(ctx.config.repo_root, security.mcp_servers_for("lead"))
    by_server: dict[str, list[str]] = {}
    for tool in security.allowed_mcp_tools("lead"):
        _, server, name = tool.split("__", 2)
        if server in present:
            by_server.setdefault(server, []).append(name)
    if not by_server:
        return ""
    parts = [f"{server} ({', '.join(names)})" for server, names in sorted(by_server.items())]
    return "- Signal read-only tools: " + "; ".join(parts) + "."
