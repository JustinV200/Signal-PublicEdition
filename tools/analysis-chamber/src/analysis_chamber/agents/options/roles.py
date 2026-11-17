"""The option builders phases call: lead_options, critic_options, qa_options.

The lead gets the in-process `chamber` server, the Signal servers its allowlist
needs, the PostToolUse free-text swap and its PostToolUseFailure warning. The
critic and the Q&A agent get no MCP servers at all: they work only on the run
folder.
"""

from claude_agent_sdk import ClaudeAgentOptions

from analysis_chamber import security
from analysis_chamber.agents.chamber_server import SERVER_NAME, build_chamber_server
from analysis_chamber.agents.context import RunContext
from analysis_chamber.agents.fetch import (
    ChamberIO,
    ChamberTools,
    HttpDownloader,
    SourceSink,
    signal_failure_matcher,
    signal_swap_matcher,
)
from analysis_chamber.agents.nested import SdkExtractor, SdkSearcher, SdkSignup
from analysis_chamber.agents.options.base import role_options
from analysis_chamber.agents.options.prompts import critic_prompt, lead_prompt, qa_prompt
from analysis_chamber.agents.signal_mcp import load_signal_servers


def default_io(ctx: RunContext) -> ChamberIO:
    """The real downloader, extractor and searcher for a run."""
    model = ctx.config.fetch_model
    return ChamberIO(
        download=HttpDownloader(),
        extract=SdkExtractor(model, ctx.run_dir),
        search=SdkSearcher(model, ctx.run_dir),
    )


def lead_options(
    ctx: RunContext, on_source: SourceSink | None = None, io: ChamberIO | None = None
) -> ClaudeAgentOptions:
    """The lead's options.

    Args:
        ctx: The run.
        on_source: Gets each manifest.sources record. Defaults to appending to
            ctx.manifest.sources in memory; the phase checkpoints the manifest.
        io: The chamber tools' I/O (default_io(ctx) if None; tests pass fakes).

    Returns:
        The options.
    """
    io = io or default_io(ctx)
    tools = ChamberTools(ctx.run_dir, io, on_source or ctx.manifest.sources.append)
    servers = load_signal_servers(ctx.config.repo_root, security.mcp_servers_for("lead"))
    servers[SERVER_NAME] = build_chamber_server(tools, SdkSignup(ctx))
    swap = signal_swap_matcher(ctx, io.extract)
    failure = signal_failure_matcher()
    extra = {"PostToolUse": [swap], "PostToolUseFailure": [failure]}
    hooks = security.build_hooks(ctx, "lead", extra=extra)
    return role_options(
        ctx, "lead", lead_prompt(ctx.config.playbook_path), mcp_servers=servers, hooks=hooks
    )


def plan_options(ctx: RunContext) -> ClaudeAgentOptions:
    """The lead's options for plan and revise turns: no MCP servers at all.

    Same model, prompt, hooks and disallowed list as lead_options, but without
    the chamber or Signal servers, so a plan turn can't collect anything before
    approval (spec 7.1).
    """
    return role_options(ctx, "lead", lead_prompt(ctx.config.playbook_path))


def critic_options(ctx: RunContext) -> ClaudeAgentOptions:
    """The critic's options: a fresh session (never resumed) with no MCP servers."""
    return role_options(ctx, "critic", critic_prompt(ctx.config.playbook_path))


def qa_options(ctx: RunContext, resume: str | None, fork: bool = False) -> ClaudeAgentOptions:
    """The Q&A agent's options.

    Args:
        ctx: The run.
        resume: A session id to resume, or None for a new session.
        fork: With `resume`, branch into a new session (fork_session) so the
            resumed session (e.g. a mid-run lead) is left untouched.

    Returns:
        The options.

    Raises:
        ValueError: fork=True with no session to resume.
    """
    if fork and resume is None:
        raise ValueError("qa_options: fork=True needs a session id to resume")
    return role_options(
        ctx, "qa", qa_prompt(ctx.config.playbook_path), resume=resume, fork_session=fork
    )
