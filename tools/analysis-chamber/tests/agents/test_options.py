"""The option builders: every role carries the send block, and MCP servers stay scoped."""

import json

import pytest

from analysis_chamber import security
from analysis_chamber.agents import critic_options, lead_options, plan_options, qa_options

# plan_options is the lead with no MCP servers, so it shares the lead's security role.
SECURITY_ROLE = {"plan": "lead"}
BUILDERS = {
    "lead": lambda ctx: lead_options(ctx),
    "plan": lambda ctx: plan_options(ctx),
    "critic": lambda ctx: critic_options(ctx),
    "qa": lambda ctx: qa_options(ctx, "sess-1"),
}


@pytest.mark.parametrize("role", list(BUILDERS))
def test_every_role_has_bypass_send_block_and_hooks(role, ctx):
    options = BUILDERS[role](ctx)
    assert options.permission_mode == "bypassPermissions"
    assert options.disallowed_tools == security.disallowed_tools(SECURITY_ROLE.get(role, role))
    assert options.hooks["PreToolUse"], "send_block_hook must be wired in"
    # No settings files, and no claude.ai connectors (spike: they load without strict).
    assert options.setting_sources == []
    assert options.strict_mcp_config is True
    assert options.cwd == str(ctx.run_dir)
    # Live run 5: a mail_search over the CLI's default MCP output cap reached the swap
    # hook as a "too large" notice and its data was lost.
    assert int(options.env["MAX_MCP_OUTPUT_TOKENS"]) >= 100_000


def test_lead_loads_only_allowlisted_servers_rewritten_for_any_cwd(ctx):
    servers = {
        name: {"command": "uv", "args": ["run", "--project", "packages/mcpshim", name]}
        for name in ("mail", "rcs", "brief", "sessions", "browser", "audiohub")
    }
    (ctx.config.repo_root / ".mcp.json").write_text(json.dumps({"mcpServers": servers}))
    options = lead_options(ctx)
    assert set(options.mcp_servers) == security.mcp_servers_for("lead") | {"chamber"}
    assert "browser" not in options.mcp_servers  # only the signup sub-session gets it
    assert options.mcp_servers["mail"]["args"][:3] == [
        "run",
        "--directory",
        str(ctx.config.repo_root),
    ]
    assert options.hooks["PostToolUse"], "the Signal free-text swap must be wired in"


def test_plan_and_critic_get_no_mcp_and_qa_resumes_or_forks(ctx):
    (ctx.config.repo_root / ".mcp.json").write_text('{"mcpServers": {"mail": {"command": "x"}}}')
    assert plan_options(ctx).mcp_servers == {}  # spec 7.1: nothing collected before approval
    critic = critic_options(ctx)
    assert critic.mcp_servers == {} and critic.resume is None
    qa = qa_options(ctx, "sess-1")
    assert qa.resume == "sess-1" and qa.fork_session is False and qa.mcp_servers == {}
    assert qa_options(ctx, "lead-1", fork=True).fork_session is True
    with pytest.raises(ValueError):  # a fork needs a session to fork from
        qa_options(ctx, None, fork=True)
