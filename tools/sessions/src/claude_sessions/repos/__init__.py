"""Public API of claude_sessions.repos: find local git repos and their Claude Code transcripts."""

from claude_sessions.repos.containment import (
    RepoNotFoundError,
    RepoOutsideRootsError,
    require_inside_roots,
)
from claude_sessions.repos.discovery import Repo, find_repos, is_git_repo
from claude_sessions.repos.resolve import (
    locate_repo,
    looks_like_path,
    resolve_repo,
)
from claude_sessions.repos.transcripts import (
    TranscriptSummary,
    find_transcript_cwd,
    list_transcripts,
)

__all__ = [
    "Repo",
    "RepoNotFoundError",
    "RepoOutsideRootsError",
    "TranscriptSummary",
    "find_repos",
    "find_transcript_cwd",
    "is_git_repo",
    "list_transcripts",
    "locate_repo",
    "looks_like_path",
    "require_inside_roots",
    "resolve_repo",
]
