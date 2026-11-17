"""The system prompt appended to Claude Code's own for each chamber role."""

from pathlib import Path

from claude_agent_sdk.types import SystemPromptPreset

# The chamber tools as the lead sees them.
FETCH_TOOL = "mcp__chamber__chamber_fetch"
EXTRACT_TOOL = "mcp__chamber__chamber_extract_file"
SEARCH_TOOL = "mcp__chamber__chamber_search"
KEY_TOOL = "mcp__chamber__chamber_get_api_key"

_LEAD = """You are the lead agent of an analysis chamber run. Your working folder is the run \
folder. Before anything else, read the methods playbook at {skill} and follow it.
Search the web with {search}, and read web pages and other HTML or text only through {fetch} \
(it returns an extract, never the raw page). Data files (CSV, JSON, XLSX, API responses) you \
may download directly into data/raw. For free text saved under data/raw, use {extract}. Signal \
read tools that return free text come back as extracts; their raw output is under \
data/raw/signal/ for exact counts in code (never print its free text). If a public API needs a \
free key, use {key}, then read the key by name from Signal's .env in code and never print it. \
Never send, post or delete anything."""

_CRITIC = """You are the critic of an analysis chamber run, with no shared context with the \
lead. Your working folder is the run folder. Read {critic} and review the run's methods, code \
and claims for leakage, statistical errors and unsupported claims. You may run code to check \
a claim, but don't change the lead's files. Never send, post or delete anything."""

_QA = """You answer questions about an analysis chamber run. Your working folder is the run \
folder (data, code, results). You may run code there to answer. The methods playbook is at \
{skill}. Never send, post or delete anything."""


def _preset(append: str) -> SystemPromptPreset:
    """Claude Code's own system prompt with `append` after it."""
    return {"type": "preset", "preset": "claude_code", "append": append}


def lead_prompt(playbook: Path) -> SystemPromptPreset:
    """The lead's system prompt, pointing at the playbook folder's SKILL.md."""
    return _preset(
        _LEAD.format(
            skill=playbook / "SKILL.md",
            fetch=FETCH_TOOL,
            extract=EXTRACT_TOOL,
            search=SEARCH_TOOL,
            key=KEY_TOOL,
        )
    )


def critic_prompt(playbook: Path) -> SystemPromptPreset:
    """The critic's system prompt, pointing at the playbook's critic.md."""
    return _preset(_CRITIC.format(critic=playbook / "critic.md"))


def qa_prompt(playbook: Path) -> SystemPromptPreset:
    """The Q&A agent's system prompt."""
    return _preset(_QA.format(skill=playbook / "SKILL.md"))
