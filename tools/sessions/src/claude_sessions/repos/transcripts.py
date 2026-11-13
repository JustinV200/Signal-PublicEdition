"""Lists existing Claude Code sessions (transcripts) for a repo, or across all projects.

Claude Code keeps one JSONL transcript per session under
`~/.claude/projects/<encoded cwd>/`. The SDK's `list_sessions` and
`get_session_info` already find and summarise them (respecting
CLAUDE_CONFIG_DIR), so this module only trims their results to what a model
or the CLI needs to pick a session to resume.
"""

from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import SDKSessionInfo, get_session_info, list_sessions

from claude_sessions.text import truncate

DEFAULT_SESSION_LIMIT = 20
# Long enough to recognise a session, short enough for a list of twenty.
MAX_PROMPT_CHARS = 120


@dataclass(frozen=True)
class TranscriptSummary:
    """One existing Claude Code session.

    Attributes:
        session_id: The Claude session UUID, usable with resume.
        last_modified_ms: When the transcript last changed, in ms since the epoch.
        first_prompt: The first real user prompt, truncated ("" when none).
        title: The session's custom or generated title, if it has one.
        cwd: The folder the session ran in, when the transcript records it.
    """

    session_id: str
    last_modified_ms: int
    first_prompt: str
    title: str | None
    cwd: str | None


def list_transcripts(
    repo_path: Path | None = None, limit: int = DEFAULT_SESSION_LIMIT
) -> list[TranscriptSummary]:
    """List the newest sessions for one repo, or across every project when no repo is given.

    Args:
        repo_path: The repo folder, or None for all projects.
        limit: Maximum number of sessions returned.

    Returns:
        Summaries sorted newest first. Worktree sessions are left out so a
        repo's list only shows sessions that ran in that folder.
    """
    directory = str(repo_path) if repo_path is not None else None
    infos = list_sessions(directory=directory, limit=limit, include_worktrees=False)
    return [_summarize(info) for info in infos]


def find_transcript_cwd(session_id: str) -> Path | None:
    """Find the folder an existing session ran in, so it can be resumed there.

    Args:
        session_id: The Claude session UUID.

    Returns:
        The session's working folder, or None when the transcript isn't found
        or doesn't record one.
    """
    info = get_session_info(session_id)
    if info is None or not info.cwd:
        return None
    return Path(info.cwd)


def _summarize(info: SDKSessionInfo) -> TranscriptSummary:
    """Trim the SDK's session info to a TranscriptSummary."""
    return TranscriptSummary(
        session_id=info.session_id,
        last_modified_ms=info.last_modified,
        first_prompt=truncate(info.first_prompt or "", MAX_PROMPT_CHARS),
        title=info.custom_title,
        cwd=info.cwd,
    )
