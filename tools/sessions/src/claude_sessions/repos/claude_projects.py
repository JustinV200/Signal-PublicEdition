"""Finds the folders Claude Code has already run in, from the transcripts in ~/.claude/projects.

The owner often opens a parent folder (e.g. C:\\src\\OtherRepo) that
holds a git repo one level down. Those folders are where their existing
sessions live, so they count as repos too. Each project folder's newest
transcripts are read only at the start, until one names its `cwd`.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

TRANSCRIPT_PATTERN = "*.jsonl"
# The cwd field is on the first records, well inside this much of the file.
HEAD_BYTES = 64 * 1024
# Transcripts tried per project folder before giving up on finding a cwd.
MAX_TRANSCRIPTS_TRIED = 3
ENCODING = "utf-8"


def default_projects_dir() -> Path:
    """Where Claude Code keeps transcripts: $CLAUDE_CONFIG_DIR/projects or ~/.claude/projects.

    Mirrors the SDK's own lookup, so listings and resumes agree on the folder.
    """
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(config_dir) if config_dir else Path.home() / ".claude") / "projects"


def find_claude_project_folders(projects_dir: Path | None = None) -> list[Path]:
    """The existing folders that Claude Code sessions have run in.

    Args:
        projects_dir: The transcripts folder (default: default_projects_dir()).

    Returns:
        Each folder once, resolved; folders that no longer exist are left out.
    """
    root = projects_dir or default_projects_dir()
    try:
        project_dirs = [entry for entry in root.iterdir() if entry.is_dir()]
    except OSError as error:
        logger.debug("No Claude projects folder at %s: %s", root, error)
        return []
    folders: dict[str, Path] = {}
    for project_dir in project_dirs:
        cwd = _cwd_of(project_dir)
        if cwd is not None and cwd.is_dir():
            resolved = cwd.resolve()
            folders.setdefault(os.path.normcase(str(resolved)), resolved)
    return list(folders.values())


def _cwd_of(project_dir: Path) -> Path | None:
    """The cwd named by one of the folder's newest transcripts, if any."""
    try:
        transcripts = sorted(
            project_dir.glob(TRANSCRIPT_PATTERN),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError as error:
        logger.debug("Can't list transcripts in %s: %s", project_dir, error)
        return None
    for transcript in transcripts[:MAX_TRANSCRIPTS_TRIED]:
        cwd = _cwd_in_head(transcript)
        if cwd:
            return Path(cwd)
    return None


def _cwd_in_head(transcript: Path) -> str | None:
    """The first "cwd" field among the complete lines at the start of a transcript."""
    try:
        with transcript.open("rb") as stream:
            head = stream.read(HEAD_BYTES)
    except OSError as error:
        logger.debug("Can't read %s: %s", transcript, error)
        return None
    # The last line may be cut off by the byte limit; it just fails to parse.
    for line in head.decode(ENCODING, errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        cwd = entry.get("cwd") if isinstance(entry, dict) else None
        if isinstance(cwd, str) and cwd:
            return cwd
    return None
