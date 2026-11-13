"""Finds the owner's repos under the configured root folders.

A repo is a folder containing `.git` (a folder, or a file for worktrees and
submodules), or a folder under a root that Claude Code has already run in (see
claude_projects.py), since the owner often works from a parent folder. The
walk is breadth-limited by depth, never follows symlinks or junctions, and
skips dependency and cache folders that never hold the owner's own repos.
"""

import logging
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from claude_sessions.repos.claude_projects import find_claude_project_folders
from claude_sessions.repos.containment import is_within

logger = logging.getLogger(__name__)

GIT_MARKER = ".git"

# Folder names never descended into: dependencies, virtualenvs, caches, build output.
SKIPPED_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".cache",
        ".next",
        ".gradle",
        ".idea",
        ".vscode",
        "site-packages",
        "dist",
        "build",
        "target",
        "$RECYCLE.BIN",
        "System Volume Information",
    }
)


@dataclass(frozen=True)
class Repo:
    """One discovered repo folder.

    Attributes:
        name: The folder's name, e.g. "OtherRepo".
        path: Absolute path of the folder.
        is_git: True for a git repo; False for a folder known only from Claude sessions.
    """

    name: str
    path: Path
    is_git: bool = True


def find_repos(
    roots: Iterable[Path], max_depth: int, claude_projects_dir: Path | None = None
) -> list[Repo]:
    """List the repos under each root, sorted by name then path.

    Args:
        roots: Folders to search. Missing roots are skipped with a warning.
        max_depth: Folder levels below a root to search for `.git`; the root
            itself is 0. Repos nested inside other repos are found too.
        claude_projects_dir: Claude Code's transcripts folder (default
            ~/.claude/projects); folders its sessions ran in count when under a root.

    Returns:
        Each folder once, even when roots overlap.
    """
    existing_roots = [root.resolve() for root in roots if _is_existing_root(root)]
    found: dict[str, Repo] = {}
    for root in existing_roots:
        for repo_path in _walk_for_repos(root, max_depth):
            found.setdefault(_key(repo_path), Repo(repo_path.name, repo_path))
    for folder in find_claude_project_folders(claude_projects_dir):
        if any(is_within(folder, root) for root in existing_roots):
            found.setdefault(_key(folder), Repo(folder.name, folder, is_git_repo(folder)))
    return sorted(found.values(), key=lambda repo: (repo.name.lower(), str(repo.path).lower()))


def is_git_repo(path: Path) -> bool:
    """Say whether a folder is a git repo (has a `.git` folder or file).

    Args:
        path: The folder to check.

    Returns:
        True when `path/.git` exists.
    """
    return (path / GIT_MARKER).exists()


def _is_existing_root(root: Path) -> bool:
    """A root that exists; a missing one is skipped with a warning."""
    if root.is_dir():
        return True
    logger.warning("Repo root %s doesn't exist; skipping it", root)
    return False


def _key(path: Path) -> str:
    """A dedupe key that treats paths differing only in case as one (Windows)."""
    return os.path.normcase(str(path))


def _walk_for_repos(root: Path, max_depth: int) -> Iterator[Path]:
    """Breadth-first walk yielding every repo folder within max_depth of root."""
    level = [root]
    for depth in range(max_depth + 1):
        next_level: list[Path] = []
        for folder in level:
            if is_git_repo(folder):
                yield folder
            if depth < max_depth:
                next_level.extend(_child_folders(folder))
        level = next_level


def _child_folders(folder: Path) -> list[Path]:
    """The real (non-link, non-skipped) subfolders of folder; [] when it can't be read."""
    try:
        with os.scandir(folder) as entries:
            return [Path(entry.path) for entry in entries if _is_walkable(entry)]
    except OSError as error:
        # Permission-denied system folders are normal under a drive root.
        logger.debug("Can't list %s: %s", folder, error)
        return []


def _is_walkable(entry: os.DirEntry[str]) -> bool:
    """A real folder worth descending into: not a link, junction or skipped name."""
    if entry.name in SKIPPED_DIR_NAMES:
        return False
    try:
        # Junctions and symlinks can loop or point at other drives; never follow them.
        return entry.is_dir(follow_symlinks=False) and not entry.is_junction()
    except OSError:
        return False
